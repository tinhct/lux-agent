.PHONY: install playground

install:
	agents-cli install

playground:
	uv run python -m app.fast_api_app
