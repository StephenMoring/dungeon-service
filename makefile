db: 
	docker build . -t dungeoncrawler:latest

dr: 
	docker run -d -p 8000:8000 --name dungeoncrawler dungeoncrawler

lr:
	docker compose --profile noapp -f infra/local/docker-compose.yml up -d --wait
	uv run uvicorn src.main:app --reload

lr-down:
	docker compose --profile noapp -f infra/local/docker-compose.yml down -v

dr:
	docker compose --profile all -f infra/local/docker-compose.yml up

dr-down:
	docker compose --profile all -f infra/local/docker-compose.yml down -v

