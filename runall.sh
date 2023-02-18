for benchmark in gramschmidt; do
  echo "Running $benchmark"
  ./$benchmark --device=gpu --output=output.csv
done
