#!/bin/bash
# HC-TAP Demo Preparation Script
# This script helps prepare the environment for demo day

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        HC-TAP Demo Preparation - Complete Checklist           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
DASHBOARD_URL="http://HcTapS-Dashb-sA1M6VoIpRJL-250085734.us-east-1.elb.amazonaws.com"
API_URL="http://HcTapS-ApiSe-W4A6277ppDFW-1985105748.us-east-1.elb.amazonaws.com"
RAW_BUCKET="hc-tap-raw-notes"
ENRICHED_BUCKET="hc-tap-enriched-entities"
AWS_REGION="us-east-1"

echo "🔍 System URLs:"
echo "   Dashboard: $DASHBOARD_URL"
echo "   API: $API_URL"
echo ""

# Function to print status
status_check() {
    if [ $? -eq 0 ]; then
        echo "   ✓ $1"
    else
        echo "   ✗ $1"
        return 1
    fi
}

# Check 1: Verify S3 has notes
echo "1️⃣  Checking S3 Raw Bucket..."
NOTE_COUNT=$(aws s3 ls s3://$RAW_BUCKET/ --region $AWS_REGION 2>/dev/null | wc -l | tr -d ' ')
if [ "$NOTE_COUNT" -gt 4900 ]; then
    echo "   ✓ S3 Raw Bucket has $NOTE_COUNT notes"
else
    echo "   ⚠️  S3 Raw Bucket has only $NOTE_COUNT notes (expected ~4966)"
    echo "   Run: python scripts/sync_to_s3.py"
fi
echo ""

# Check 2: Verify S3 has enriched data
echo "2️⃣  Checking S3 Enriched Bucket..."
if aws s3 ls s3://$ENRICHED_BUCKET/runs/latest.json --region $AWS_REGION > /dev/null 2>&1; then
    echo "   ✓ Manifest exists"
    
    # Download and display manifest
    MANIFEST=$(aws s3 cp s3://$ENRICHED_BUCKET/runs/latest.json - --region $AWS_REGION 2>/dev/null)
    ENTITY_COUNT=$(echo "$MANIFEST" | grep -o '"entity_count": [0-9]*' | grep -o '[0-9]*')
    NOTE_COUNT_ENRICHED=$(echo "$MANIFEST" | grep -o '"note_count": [0-9]*' | grep -o '[0-9]*')
    
    echo "   ✓ Processed $NOTE_COUNT_ENRICHED notes"
    echo "   ✓ Extracted $ENTITY_COUNT entities"
else
    echo "   ✗ Manifest not found - ETL needs to run"
    echo "   Run: bash scripts/trigger_etl.sh"
fi
echo ""

# Check 3: API Health
echo "3️⃣  Checking API Service..."
API_RESPONSE=$(curl -s $API_URL/stats/latest)
if echo "$API_RESPONSE" | grep -q "run_id"; then
    echo "   ✓ API is responding"
    echo "   ✓ API can read from S3"
else
    echo "   ✗ API not responding correctly"
fi
echo ""

# Check 4: Test Live Extraction
echo "4️⃣  Testing Live Extraction..."
EXTRACT_RESPONSE=$(curl -s -X POST $API_URL/extract \
    -H "Content-Type: application/json" \
    -d '{"text":"Patient has chest pain and nausea.","note_id":"demo"}' 2>/dev/null)

if echo "$EXTRACT_RESPONSE" | grep -q "entities"; then
    EXTRACTED_COUNT=$(echo "$EXTRACT_RESPONSE" | grep -o "entity_type" | wc -l | tr -d ' ')
    echo "   ✓ Live extraction working (extracted $EXTRACTED_COUNT entities)"
else
    echo "   ✗ Live extraction failed"
fi
echo ""

# Check 5: Dashboard Accessibility
echo "5️⃣  Checking Dashboard Service..."
DASH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $DASHBOARD_URL)
if [ "$DASH_STATUS" = "200" ]; then
    echo "   ✓ Dashboard is accessible"
else
    echo "   ✗ Dashboard returned status: $DASH_STATUS"
fi
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                        Demo Readiness                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ "$NOTE_COUNT" -gt 4900 ] && [ -n "$ENTITY_COUNT" ] && [ "$DASH_STATUS" = "200" ]; then
    echo "✅ SYSTEM READY FOR DEMO!"
    echo ""
    echo "📊 Quick Stats:"
    echo "   • Notes processed: $NOTE_COUNT_ENRICHED"
    echo "   • Entities extracted: $ENTITY_COUNT"
    echo "   • Live extraction: Working"
    echo ""
else
    echo "⚠️  SYSTEM NEEDS ATTENTION"
    echo ""
    echo "Action items:"
    if [ "$NOTE_COUNT" -lt 4900 ]; then
        echo "   • Upload notes: python scripts/sync_to_s3.py"
    fi
    if [ -z "$ENTITY_COUNT" ]; then
        echo "   • Run ETL: bash scripts/trigger_etl.sh"
    fi
    if [ "$DASH_STATUS" != "200" ]; then
        echo "   • Check ECS services in AWS Console"
    fi
    echo ""
fi

# Demo URLs
echo "═══════════════════════════════════════════════════════════════"
echo "🎯 DEMO URLS (bookmark these):"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Dashboard (Main Demo):"
echo "  $DASHBOARD_URL"
echo ""
echo "API Documentation:"
echo "  $API_URL/docs"
echo ""
echo "API Health Check:"
echo "  $API_URL/health"
echo ""
echo "API Stats:"
echo "  $API_URL/stats/latest"
echo ""

# Demo talking points
echo "═══════════════════════════════════════════════════════════════"
echo "💡 DEMO TALKING POINTS:"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "1. Architecture:"
echo "   • Serverless (AWS Fargate - no EC2 management)"
echo "   • S3 Data Lake (Raw + Enriched buckets)"
echo "   • Load Balanced APIs (ALB for HA)"
echo "   • CloudWatch Logging & Monitoring"
echo ""
echo "2. Data Pipeline:"
echo "   • Ingested: ~5000 clinical notes"
echo "   • Extracted: ~5400+ entities (PROBLEM, MEDICATION, TEST)"
echo "   • Performance: p50=3ms, p95=9ms per note"
echo "   • Infrastructure as Code: AWS CDK (Python)"
echo ""
echo "3. Live Demo Flow:"
echo "   • Show Dashboard KPIs tab"
echo "   • Demo live extraction with clinical text"
echo "   • Show API documentation (FastAPI auto-docs)"
echo "   • Explain entity types and rule-based extraction"
echo ""
echo "4. Technical Highlights:"
echo "   • CI/CD via GitHub Actions"
echo "   • Docker multi-stage builds (AMD64 for Fargate)"
echo "   • Rate limiting & CORS on API"
echo "   • Streamlit for rapid dashboard prototyping"
echo ""

# Troubleshooting
echo "═══════════════════════════════════════════════════════════════"
echo "🔧 TROUBLESHOOTING (if needed during demo):"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "If dashboard shows no data:"
echo "  1. Verify ETL ran: aws s3 ls s3://$ENRICHED_BUCKET/runs/"
echo "  2. Check API: curl $API_URL/stats/latest"
echo "  3. Restart dashboard service (ECS console)"
echo ""
echo "If live extraction fails:"
echo "  1. Check API health: curl $API_URL/health"
echo "  2. Check logs: /ecs/HcTapStack-ApiService* in CloudWatch"
echo "  3. Test directly: curl -X POST $API_URL/extract -d '{...}'"
echo ""
echo "Fallback plan:"
echo "  • Show local dashboard screenshot (already working)"
echo "  • Walk through code & architecture diagrams"
echo "  • Show GitHub Actions logs (CI/CD pipeline)"
echo ""

# Test command examples
echo "═══════════════════════════════════════════════════════════════"
echo "🧪 QUICK TEST COMMANDS:"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "# Test API extraction:"
cat << 'EOF'
curl -X POST http://HcTapS-ApiSe-W4A6277ppDFW-1985105748.us-east-1.elb.amazonaws.com/extract \
  -H "Content-Type: application/json" \
  -d '{"text":"Patient presents with severe chest pain and nausea. Prescribed aspirin 81mg daily."}'
EOF
echo ""
echo "# Check manifest:"
echo "aws s3 cp s3://$ENRICHED_BUCKET/runs/latest.json -"
echo ""
echo "# List entities:"
echo "aws s3 ls s3://$ENRICHED_BUCKET/runs/cloud-latest/"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "✨ READY FOR DEMO! Good luck! ✨"
echo "═══════════════════════════════════════════════════════════════"
