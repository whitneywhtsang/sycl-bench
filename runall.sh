for benchmark in 2DConvolution 2mm 3mm atax bicg covariance gemm gesummv gramschmidt matmulchain mvt syr2k syrk; do
  echo "Running $benchmark"
  ./$benchmark --device=gpu --output=output.csv
done
