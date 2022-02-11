docker build --target ws-server -t wordle-solving/ws-server .
docker build --target ws-web -t wordle-solving/ws-web:latest .
docker-compose up -d
