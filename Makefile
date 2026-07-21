.PHONY: build network server-image lb-up up down clean logs

NETWORK = net1

network:
	docker network inspect $(NETWORK) >/dev/null 2>&1 || docker network create $(NETWORK)

server-image:
	docker build -t server-image ./server

build: network server-image
	docker compose build

up: build
	docker compose up -d

down:
	docker compose down
	-for c in $$(docker ps -a --format '{{.Names}}' | grep -E '^S[A-Z0-9]{6}$$'); do \
		docker rm -f $$c; \
	done

clean: down
	-docker rmi loadbalancer-image server-image
	-docker network rm $(NETWORK)

logs:
	docker compose logs -f loadbalancer
