build:
	docker build -t fund-bot:0.0.7 -f deploy/dockerfile .

mac_build:
	 docker buildx build --load --platform linux/amd64 -t fund-bot:0.0.7 -f deploy/Dockerfile .

docker_save:
	docker save -o ~/Downloads/fund_bot7.tar fund-bot:0.0.7