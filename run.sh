run_db() {
  docker run --rm -d -p 5432:5432 -e POSTGRES_PASSWORD=password --name books-data postgres:14-alpine
}

remove_db() {
  docker kill books-data
}

migrate_db() {
  docker run --network="host" -v "$(pwd)/migrations":/flyway/sql flyway/flyway:8.5.9-alpine \
    -url=jdbc:postgresql://localhost:5432/postgres \
    -user=postgres -password=password migrate
}

case "$1" in
  "run_db") run_db ;;
  "remove_db") remove_db ;;
  "migrate_db") migrate_db ;;
  *) echo "run_db | remove_db | migrate_db";;
esac