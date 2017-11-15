# Build a container via the command "make build"
# By Jason Gegere <jason@htmlgraphic.com>

VERSION 	= 1.7.1
NAME 		= apache
IMAGE_REPO 	= htmlgraphic
IMAGE_NAME 	= $(IMAGE_REPO)/$(NAME)
DOMAIN 		= htmlgraphic.com
include .env


all:: help


help:
	@echo ""
	@echo "-- Help Menu"
	@echo ""
	@echo "     make build		- Build image $(IMAGE_NAME):$(VERSION)"
	@echo "     make push		- Push $(IMAGE_NAME):$(VERSION) to public docker repo"
	@echo "     make run		- Run docker-compose and create local development environment"
	@echo "     make start		- Start the EXISTING $(NAME) container"
	@echo "     make stop		- Stop local environment build"
	@echo "     make restart	- Stop and start $(NAME) container"
	@echo "     make rm		- Stop and remove $(NAME) container"
	@echo "     make state		- View state $(NAME) container"
	@echo "     make logs		- View logs in real time"


env:
	@echo $(shell sed 's/=.*//' .env)

build:
	docker build \
		--build-arg VCS_REF=`git rev-parse --short HEAD` \
		--build-arg BUILD_DATE=`date -u +"%Y-%m-%dT%H:%M:%SZ"` \
		--rm -t $(IMAGE_NAME):$(VERSION) -t $(IMAGE_NAME):envoyer .

push:
	@echo "note: If the repository is set as an automatted build you will NOT be able to push"
	docker push $(IMAGE_NAME):$(VERSION)

run:
	@echo 'Checking... for initial folder structure:'
	@if [ ! -d "/Volumes/Case" ]; then \
		echo "		Creating project folders" && sudo mkdir -p /Volumes/Case && sudo mkdir -p /Volumes/Case/SITES && sudo mkdir -p /Volumes/Case/SITES/docker; fi
	@[ ! -f .env ] && echo "		.env file does not exist, copy env template" && cp .env.example .env || echo "		env file exists"
	@echo ""
	@echo "Upon initial setup run the following on the MySQL system, this will setup a GLOBAL admin:"
	@echo ""
	@echo "		docker exec -it apache_db_1 /bin/bash \n \
			mysql -p$(MYSQL_ROOT_PASSWORD) \n \
			GRANT ALL PRIVILEGES ON * . * TO '$(MYSQL_USER)'@'%' with grant option; \n"

	@echo "		THE PASSWORD FOR $(MYSQL_USER) IS $(MYSQL_PASSWORD); \n"
	docker-compose -f docker-compose.local.yml up -d

start: run

stop:
	@echo "Stopping local environment setup"
	docker-compose stop

restart:	stop start

rm:
	@echo "On remove, containers are specifally referenced, as to not destroy ANY persistent data"
	@echo "Removing $(NAME) and $(NAME)_db_1"
	docker rm -f $(NAME)
	docker rm -f $(NAME)_db_1

state:
	docker ps -a | grep $(NAME)

logs:
	@echo "Build $(NAME)..."
	docker logs -f $(NAME)
