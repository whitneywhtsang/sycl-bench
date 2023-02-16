#include <string>
#include <vector>

#include <cmath>
#include <cstdlib>

#include <CL/sycl.hpp>

#include "common.h"
#include "polybenchUtilFuncts.h"

using DATA_TYPE = float;

class CovarianceMean;
class CovarianceReduce;
class CovarianceCovar;

constexpr DATA_TYPE float_n = 3214212.01;

void init_arrays(DATA_TYPE* data, size_t size) {
	const auto M = size;
	const auto N = size;

	for(size_t i = 0; i < M; i++) {
		for(size_t j = 0; j < N; j++) {
			data[i * (N + 1) + j] = ((DATA_TYPE)i * j) / M;
		}
	}
}

void covariance(DATA_TYPE* data, DATA_TYPE* symmat, DATA_TYPE* mean, size_t size) {
	const auto M = size;
	const auto N = size;

	// Determine mean of column vectors of input data matrix
	for(size_t j = 1; j <= M; j++) {
		mean[j] = 0.0;
		for(size_t i = 1; i <= N; i++) {
			mean[j] += data[i * (M + 1) + j];
		}
		mean[j] /= float_n;
	}

	// Center the column vectors.
	for(size_t i = 1; i <= N; i++) {
		for(size_t j = 1; j <= M; j++) {
			data[i * (M + 1) + j] -= mean[j];
		}
	}

	// Calculate the m * m covariance matrix.
	for(size_t j1 = 1; j1 <= M; j1++) {
		for(size_t j2 = j1; j2 <= M; j2++) {
			symmat[j1 * (M + 1) + j2] = 0.0;
			for(size_t i = 1; i <= N; i++) {
				symmat[j1 * (M + 1) + j2] += data[i * (M + 1) + j1] * data[i * (M + 1) + j2];
			}
			symmat[j2 * (M + 1) + j1] = symmat[j1 * (M + 1) + j2];
		}
	}
}

class Polybench_Covariance {
public:
	Polybench_Covariance(const BenchmarkArgs& args) : args(args), size(args.problem_size) {}

	void setup() {
		data.resize((size + 1) * (size + 1));
		symmat.resize((size + 1) * (size + 1));
		mean.resize(size + 1);

		init_arrays(data.data(), size);

		data_buffer.initialize(args.device_queue, data.data(), cl::sycl::range<2>(size + 1, size + 1));
		symmat_buffer.initialize(args.device_queue, symmat.data(), cl::sycl::range<2>(size + 1, size + 1));
		mean_buffer.initialize(args.device_queue, mean.data(), cl::sycl::range<1>(size + 1));
  }

	void run(std::vector<cl::sycl::event>& events) {
		using namespace cl::sycl;

		events.push_back(args.device_queue.submit([&](handler& cgh) {
			auto data = data_buffer.get_access<access::mode::read>(cgh);
			auto mean = mean_buffer.get_access<access::mode::discard_write>(cgh);

			cgh.parallel_for<CovarianceMean>(range<1>(size), id<1>(1), [=, N_ = size](item<1> item) {
				const auto j = item[0];

        DATA_TYPE mean_reduction = 0;
				for(size_t i = 1; i <= N_; i++) {
					mean_reduction += data[{i, j}];
				}
				mean[item] = mean_reduction / float_n;
			});
		}));

		events.push_back(args.device_queue.submit([&](handler& cgh) {
			auto mean = mean_buffer.get_access<access::mode::read>(cgh);
			auto data = data_buffer.get_access<access::mode::read_write>(cgh);

			cgh.parallel_for<CovarianceReduce>(range<2>(size, size), id<2>(1, 1), [=](item<2> item) {
				const auto j = item[1];
				data[item] -= mean[j];
			});
		}));

		events.push_back(args.device_queue.submit([&](handler& cgh) {
			auto data = data_buffer.get_access<access::mode::read>(cgh);
			auto symmat = symmat_buffer.get_access<access::mode::discard_write>(cgh);
			auto symmat2 = symmat_buffer.get_access<access::mode::discard_write>(cgh);

			cgh.parallel_for<CovarianceCovar>(range<1>(size), id<1>(1), [=, M_ = size, N_ = size](item<1> item) {
				const auto j1 = item[0];

				symmat[{j1, j1}] = 1.0;

				for(size_t j2 = j1; j2 <= M_; j2++) {
					DATA_TYPE symmat_reduction = 0.0;
					for(size_t i = 1; i <= N_; i++) {
						symmat_reduction += data[{i, j1}] * data[{i, j2}];
					}
					symmat[{j1, j2}] = symmat_reduction;

					symmat2[{j2, j1}] = symmat_reduction;
				}
			});
		}));
	}

	bool verify(VerificationSetting&) {
		constexpr auto ERROR_THRESHOLD = 0.05;

		std::vector<DATA_TYPE> data_cpu((size + 1) * (size + 1));
		std::vector<DATA_TYPE> symmat_cpu((size + 1) * (size + 1));
		std::vector<DATA_TYPE> mean_cpu(size + 1);

		// Trigger writeback
		symmat_buffer.reset();

		init_arrays(data_cpu.data(), size);

		covariance(data_cpu.data(), symmat_cpu.data(), mean_cpu.data(), size);

		for(size_t i = 1; i < size + 1; i++) {
			for(size_t j = 1; j < size + 1; j++) {
				const auto diff = percentDiff(symmat_cpu[i * (size + 1) + j], symmat[i * (size + 1) + j]);
				if(diff > ERROR_THRESHOLD) return false;
			}
		}

		return true;
	}

	static std::string getBenchmarkName() { return "Polybench_Covariance"; }

private:
	BenchmarkArgs args;

	const size_t size;
	std::vector<DATA_TYPE> data;
	std::vector<DATA_TYPE> symmat;
	std::vector<DATA_TYPE> mean;

	PrefetchedBuffer<DATA_TYPE, 2> data_buffer;
	PrefetchedBuffer<DATA_TYPE, 2> symmat_buffer;
	PrefetchedBuffer<DATA_TYPE, 1> mean_buffer;
};

int main(int argc, char** argv) {
	BenchmarkApp app(argc, argv);
	app.run<Polybench_Covariance>();
	return 0;
}
