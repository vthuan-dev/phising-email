# Phishing Detection Pipeline - Runbook

## Table of Contents

1. [Docker and Memory Issues](#docker-and-memory-issues)
2. [Elasticsearch Bootstrap Checks](#elasticsearch-bootstrap-checks)
3. [Logstash Pipeline Errors](#logstash-pipeline-errors)
4. [Filebeat Permissions](#filebeat-permissions)
5. [ElastAlert Authentication](#elastalert-authentication)
6. [Common Service Issues](#common-service-issues)
7. [Performance Tuning](#performance-tuning)
8. [Monitoring and Debugging](#monitoring-and-debugging)

## Docker and Memory Issues

### Problem: Elasticsearch fails to start with memory errors

**Symptoms:**
```
elasticsearch exited with code 78
max virtual memory areas vm.max_map_count [65530] is too low
```

**Solution:**

Linux/macOS:
```bash
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
```

Windows (Docker Desktop):
```powershell
wsl -d docker-desktop
sysctl -w vm.max_map_count=262144
```

### Problem: Container out of memory

**Symptoms:**
```
Container killed due to memory limit
Exit code 137
```

**Solution:**
1. Increase Docker memory allocation (4GB+ recommended)
2. Adjust heap sizes in `.env`:
   ```bash
   ES_JAVA_OPTS=-Xms1g -Xmx2g
   LS_JAVA_OPTS=-Xms512m -Xmx1g
   ```

### Problem: Docker Compose fails to build

**Symptoms:**
```
failed to solve: process "/bin/sh -c pip install -r requirements.txt" did not complete successfully
```

**Solutions:**
1. Clear Docker cache:
   ```bash
   docker system prune -a
   ```
2. Rebuild without cache:
   ```bash
   docker-compose build --no-cache
   ```

## Elasticsearch Bootstrap Checks

### Problem: Bootstrap check failures

**Common Issues:**

1. **Max file descriptors**
   ```bash
   # Linux
   sudo ulimit -n 65536
   echo '* soft nofile 65536' | sudo tee -a /etc/security/limits.conf
   echo '* hard nofile 65536' | sudo tee -a /etc/security/limits.conf
   ```

2. **Memory lock**
   ```yaml
   # docker-compose.yml
   elasticsearch:
     ulimits:
       memlock:
         soft: -1
         hard: -1
   ```

3. **Disable bootstrap checks for development**
   ```yaml
   # docker-compose.yml
   elasticsearch:
     environment:
       - discovery.type=single-node
       - cluster.initial_master_nodes=
   ```

### Problem: Elasticsearch cluster health is red

**Check cluster status:**
```bash
curl -X GET "localhost:9200/_cluster/health?pretty"
curl -X GET "localhost:9200/_cat/indices?v"
```

**Common fixes:**
1. Delete corrupted indices:
   ```bash
   curl -X DELETE "localhost:9200/phish-mail-2024.01.01"
   ```

2. Reset cluster settings:
   ```bash
   curl -X PUT "localhost:9200/_cluster/settings" -H 'Content-Type: application/json' -d'
   {
     "persistent": {
       "cluster.routing.allocation.enable": "all"
     }
   }'
   ```

## Logstash Pipeline Errors

### Problem: Logstash fails to start

**Check logs:**
```bash
docker-compose logs logstash
```

**Common issues:**

1. **Invalid pipeline configuration**
   ```bash
   # Test configuration
   docker-compose exec logstash logstash --config.test_and_exit
   ```

2. **Missing geoip database**
   ```ruby
   # Add to pipeline.conf
   filter {
     if [sender_ip] {
       geoip {
         source => "sender_ip"
         target => "geoip"
         add_tag => [ "geoip" ]
       }
     }
   }
   ```

### Problem: JSON parsing errors

**Symptoms in logs:**
```
_jsonparsefailure in tags
```

**Solutions:**
1. Validate JSON format:
   ```bash
   # Check log file format
   tail -f /var/log/email_events.log | jq .
   ```

2. Add error handling to pipeline:
   ```ruby
   filter {
     json {
       source => "message"
       skip_on_invalid_json => true
       add_tag => [ "json_parsed" ]
     }
   }
   ```

### Problem: High memory usage in Logstash

**Solutions:**
1. Adjust heap size:
   ```yaml
   environment:
     - "LS_JAVA_OPTS=-Xmx1g -Xms1g"
   ```

2. Tune pipeline workers:
   ```yaml
   # logstash.yml
   pipeline.workers: 2
   pipeline.batch.size: 125
   ```

## Filebeat Permissions

### Problem: Permission denied errors

**Symptoms:**
```
ERROR failed to publish events: write /var/log/email_events.log: permission denied
```

**Solutions:**

1. **Fix file permissions:**
   ```bash
   sudo chmod 644 /var/log/email_events.log
   sudo chown root:root /var/log/email_events.log
   ```

2. **Run Filebeat as root:**
   ```yaml
   # docker-compose.yml
   filebeat:
     user: root
   ```

3. **Check volume mounts:**
   ```yaml
   filebeat:
     volumes:
       - log_data:/var/log:ro
   ```

### Problem: Filebeat not tailing files

**Check Filebeat registry:**
```bash
docker-compose exec filebeat filebeat show config
docker-compose exec filebeat ls -la /usr/share/filebeat/data/registry
```

**Reset registry:**
```bash
docker-compose stop filebeat
docker volume rm attt_filebeat_data
docker-compose up filebeat
```

### Problem: Connection refused to Logstash

**Check connectivity:**
```bash
docker-compose exec filebeat nc -zv logstash 5044
```

**Solutions:**
1. Verify Logstash is listening:
   ```bash
   docker-compose exec logstash netstat -tlnp | grep 5044
   ```

2. Check Docker network:
   ```bash
   docker network inspect attt_default
   ```

## ElastAlert Authentication

### Problem: ElastAlert cannot connect to Elasticsearch

**Symptoms:**
```
ConnectionError: [Errno 111] Connection refused
Unauthorized: 401
```

**Solutions:**

1. **Update ElastAlert config:**
   ```yaml
   # config/elastalert/config.yaml
   es_host: elasticsearch
   es_port: 9200
   es_username: elastic
   es_password: your_password
   ```

2. **Test connection:**
   ```bash
   docker-compose exec elastalert elastalert-test-rule config/rules/phish_rule.yaml
   ```

### Problem: ElastAlert rule syntax errors

**Test rule syntax:**
```bash
docker-compose exec elastalert elastalert-test-rule config/rules/phish_rule.yaml --verbose
```

**Common fixes:**
1. Check YAML indentation
2. Validate time format: `minutes: 5`
3. Check field mappings: `ml_score` vs `ml_score.keyword`

### Problem: Email notifications not working

**Test SMTP settings:**
```python
# Test script
import smtplib
from email.mime.text import MIMEText

smtp = smtplib.SMTP('smtp.gmail.com', 587)
smtp.starttls()
smtp.login('user', 'password')
# Test send...
```

**Check ElastAlert logs:**
```bash
docker-compose logs elastalert | grep -i "smtp\|email"
```

## Common Service Issues

### Agent Service

**Problem: ML model not found**
```bash
# Check artifacts
docker-compose exec agent ls -la /app/ml_artifacts/
# Retrain if missing
make train
```

**Problem: OpenAI API errors**
```bash
# Check API key
docker-compose exec agent python -c "import openai; print(openai.api_key)"
# Test API call
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### Kibana Service

**Problem: Kibana not accessible**
1. Check Elasticsearch connection:
   ```bash
   docker-compose exec kibana curl -f http://elasticsearch:9200/
   ```

2. Check Kibana logs:
   ```bash
   docker-compose logs kibana | grep -i error
   ```

3. Reset Kibana data:
   ```bash
   curl -X DELETE "localhost:9200/.kibana*"
   docker-compose restart kibana
   ```

## Performance Tuning

### Elasticsearch Performance

**Index settings:**
```bash
curl -X PUT "localhost:9200/phish-mail-*/_settings" -H 'Content-Type: application/json' -d'
{
  "index": {
    "refresh_interval": "30s",
    "number_of_replicas": 0
  }
}'
```

**Template optimization:**
```json
{
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "refresh_interval": "30s"
    }
  }
}
```

### Agent Performance

**Batch processing:**
```python
# Process emails in batches
BATCH_SIZE = 10
for batch in chunks(emails, BATCH_SIZE):
    results = [process_email(email) for email in batch]
    write_batch_to_log(results)
```

**Caching optimization:**
```python
# Enable LLM caching
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=3600  # 1 hour
```

## Monitoring and Debugging

### Health Checks

**Service health:**
```bash
# Check all services
docker-compose ps

# Individual health checks
curl localhost:9200/_cluster/health
curl localhost:5601/api/status
curl localhost:8000/health
```

**Custom health check script:**
```bash
#!/bin/bash
# scripts/health_check.sh

echo "Checking Elasticsearch..."
curl -f http://localhost:9200/_cluster/health || echo "ES down"

echo "Checking Kibana..."
curl -f http://localhost:5601/api/status || echo "Kibana down"

echo "Checking log file..."
test -f /var/log/email_events.log || echo "Log file missing"
```

### Log Analysis

**Centralized logging:**
```bash
# View all logs
docker-compose logs -f

# Filter by service
docker-compose logs -f agent | grep ERROR

# Real-time monitoring
tail -f /var/log/email_events.log | jq .
```

**Log rotation check:**
```bash
# Check log sizes
docker-compose exec agent du -sh /var/log/

# Manual rotation
docker-compose exec agent logrotate /etc/logrotate.conf
```

### Performance Metrics

**Resource usage:**
```bash
# Container stats
docker stats

# Disk usage
docker system df

# Network usage
docker-compose exec agent netstat -i
```

**Custom metrics:**
```python
# Add to agent
import psutil

def log_system_metrics():
    metrics = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent
    }
    logger.info("System metrics", extra=metrics)
```

## Emergency Procedures

### Complete System Reset

```bash
# Stop all services
make down

# Clean everything
docker system prune -af
docker volume prune -f

# Rebuild and restart
make build
make train
make up
```

### Data Recovery

**Backup Elasticsearch:**
```bash
# Create snapshot repository
curl -X PUT "localhost:9200/_snapshot/backup_repo" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/usr/share/elasticsearch/backup"
  }
}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/backup_repo/snapshot_1"
```

**Restore from backup:**
```bash
curl -X POST "localhost:9200/_snapshot/backup_repo/snapshot_1/_restore"
```

## Contact Information

- **On-call Engineer**: +1-XXX-XXX-XXXX
- **Slack Channel**: #phishing-detection-ops
- **Email**: ops@company.com
- **Documentation**: https://wiki.company.com/phishing-detection
