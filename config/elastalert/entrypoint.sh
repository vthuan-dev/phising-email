#!/bin/sh

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
until curl -s "http://elasticsearch:9200/_cluster/health" > /dev/null 2>&1; do
    echo "Waiting for Elasticsearch..."
    sleep 5
done
echo "Elasticsearch is ready!"

# Create the ElastAlert index if it doesn't exist
echo "Creating ElastAlert index..."
python -c "
import sys
import time
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://elasticsearch:9200'])

# Wait for ES to be ready
for i in range(30):
    try:
        if es.ping():
            break
    except:
        pass
    time.sleep(2)

# Create index if not exists
if not es.indices.exists('elastalert_status'):
    es.indices.create('elastalert_status', body={
        'settings': {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }
    })
    print('ElastAlert index created')
else:
    print('ElastAlert index already exists')
" || echo "Failed to create index, but continuing..."

# Start ElastAlert
echo "Starting ElastAlert..."
elastalert --verbose --config /opt/elastalert/config/config.yaml
