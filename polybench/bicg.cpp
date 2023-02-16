#include <string>
#include <vector>

#include <cstdlib>

#include <CL/sycl.hpp>

#include "common.h"
#include "polybenchUtilFuncts.h"

#ifndef M_PI
#define M_PI 3.14159
#endif

using DATA_TYPE = float;

class Bicg1;
class Bicg2;

void init_array(DATA_TYPE* A, DATA_TYPE* p, DATA_TYPE* r, size_t size) {
	const auto NX = size;
	const auto NY = size;

	for(size_t i = 0; i < NX; i++) {
		r[i] = i * M_PI;

		for(size_t j = 0; j < NY; j++) {
			A[i * NY + j] = ((DATA_TYPE)i * j) / NX;
		}
	}

	for(size_t i = 0; i < NY; i++) {
		p[i] = i * M_PI;
	}
}

void bicg_cpu(DATA_TYPE* A, DATA_TYPE* r, DATA_TYPE* s, DATA_TYPE* p, DATA_TYPE* q, size_t size) {
	const auto NX = size;
	const auto NY = size;

	for(size_t i = 0; i < NX; i++) {
		for(size_t j = 0; j < NY; j++) {
			s[j] += r[i] * A[i * NY + j];
			q[i] += A[i * NY + j] * p[j];
		}
	}
}

class Polybench_Bicg {
  public:
	Polybench_Bicg(const BenchmarkArgs& args) : args(args), size(args.problem_size) {}

	void setup() {
		A.resize(size * size);
		r.resize(size);
		s.resize(size);
		p.resize(size);
		q.resize(size);

		init_array(A.data(), p.data(), r.data(), size);

		A_buffer.initialize(args.device_queue, A.data(), cl::sycl::range<2>(size, size));
		r_buffer.initialize(args.device_queue, r.data(), cl::sycl::range<1>(size));
	  s_buffer.initialize(args.device_queue, s.data(), cl::sycl::range<1>(size));
		p_buffer.initialize(args.device_queue, p.data(), cl::sycl::range<1>(size));
		q_buffer.initialize(args.device_queue, q.data(), cl::sycl::range<1>(size));
	}

	void run(std::vector<cl::sycl::event>& events) {
		using namespace cl::sycl;

		events.push_back(args.device_queue.submit([&](handler& cgh) {
			auto A = A_buffer.get_access<access::mode::read>(cgh);
			auto r = r_buffer.get_access<access::mode::read>(cgh);
			auto s = s_buffer.get_access<access::mode::read_write>(cgh);
			auto p = p_buffer.get_access<access::mode::read>(cgh);
			auto q = q_buffer.get_access<access::mode::read_write>(cgh);

			cgh.parallel_for<Bicg1>(s_buffer.get_range(), [=, size_ = size](item<1> item) {
				const auto j = item[0];

        DATA_TYPE s_reduction = s[item];
        DATA_TYPE q_reduction = q[item];
				for(size_t i = 0; i < size_; i++) {
					s_reduction += A[{i, j}] * r[i];
					q_reduction += A[{j, i}] * p[i];
				}
				s[item] = s_reduction;
				q[item] = q_reduction;
			});
		}));
	}

	bool verify(VerificationSetting&) {
		constexpr auto ERROR_THRESHOLD = 0.05;

		// Trigger writebacks
		s_buffer.reset();
		q_buffer.reset();

		std::vector<DATA_TYPE> s_cpu(size);
		std::vector<DATA_TYPE> q_cpu(size);

		bicg_cpu(A.data(), r.data(), s_cpu.data(), p.data(), q_cpu.data(), size);

		for(size_t i = 0; i < size; i++) {
			auto diff = percentDiff(s_cpu[i], s[i]);
			if(diff > ERROR_THRESHOLD) return false;

			diff = percentDiff(q_cpu[i], q[i]);
			if(diff > ERROR_THRESHOLD) return false;
		}

		return true;
	}

	static std::string getBenchmarkName() { return "Polybench_Bicg"; }

  private:
	BenchmarkArgs args;

	const size_t size;
	std::vector<DATA_TYPE> A;
	std::vector<DATA_TYPE> r;
	std::vector<DATA_TYPE> s;
	std::vector<DATA_TYPE> p;
	std::vector<DATA_TYPE> q;

	PrefetchedBuffer<DATA_TYPE, 2> A_buffer;
	PrefetchedBuffer<DATA_TYPE, 1> r_buffer;
	PrefetchedBuffer<DATA_TYPE, 1> s_buffer;
	PrefetchedBuffer<DATA_TYPE, 1> p_buffer;
	PrefetchedBuffer<DATA_TYPE, 1> q_buffer;
};

int main(int argc, char** argv) {
	BenchmarkApp app(argc, argv);
	app.run<Polybench_Bicg>();
	return 0;
}
