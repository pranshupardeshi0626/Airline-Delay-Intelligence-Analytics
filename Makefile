.PHONY: install sample run test lint clean

install:            ## install package + dev tools
	pip install -e ".[dev]"

sample:             ## generate SYNTHETIC demo data (not real statistics)
	python scripts/generate_sample_data.py --rows 100000

run:                ## full pipeline on data/raw/flight_random_1million.csv
	python scripts/run_pipeline.py

test:               ## run unit + integration tests
	pytest --cov=airline_delay --cov-report=term-missing

lint:
	ruff check src tests scripts

clean:              ## remove generated artefacts (keeps raw data)
	rm -rf data/processed/* data/interim/* reports/figures/*.html reports/tables/*.csv reports/insights.md reports/data_quality_report.json
