#!/bin/bash
# scripts/bootstrap_kibana.sh

echo "Bootstrapping Kibana with saved objects..."

# Wait for Kibana to be ready
echo "Waiting for Kibana to be ready..."
until curl -f http://localhost:5601/api/status >/dev/null 2>&1; do
    echo "Waiting for Kibana..."
    sleep 5
done

echo "Kibana is ready. Importing saved objects..."

# Import saved objects
curl -X POST "localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  --form file=@config/kibana/saved_objects.ndjson

# Create index template
echo "Creating Elasticsearch index template..."
curl -X PUT "localhost:9200/_index_template/phish-mail-template" \
  -H "Content-Type: application/json" \
  -d @config/elastic/index-template.json

# Create ILM policy
echo "Creating ILM policy..."
curl -X PUT "localhost:9200/_ilm/policy/phish-mail-policy" \
  -H "Content-Type: application/json" \
  -d @config/elastic/ilm-policy.json

echo "Kibana bootstrap completed!"
echo "Access Kibana at: http://localhost:5601"
