.PHONY: restart migrate restart-migrate

restart:
	docker-compose up --build -d

migrate:
	docker exec qrm_api_1 python3 manage.py migrate

restart-migrate: restart migrate
