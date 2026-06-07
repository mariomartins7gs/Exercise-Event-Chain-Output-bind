# 06 — Cost Analysis (Azure for Students)

## Monthly Cost Estimate

| Resource | Tier / SKU | Monthly Cost | Notes |
|---|---|---|---|
| Function App | Consumption (Y1) | **$0.00** | 1M free executions/month, 400K GB-s |
| Storage Account | Standard_LRS | **~$0.05** | Negligible for < 1 GB data |
| Cosmos DB | Free Tier (Serverless) | **$0.00** | 1000 RU/s + 25 GB free per account |
| App Insights | Basic | **$0.00** | 5 GB/month free data ingestion |
| Event Grid | Standard | **~$0.60** | $0.60/million operations (classroom: ~100/month) |
| ACS SMS | Free Tier | **$0.00** | 200 SMS messages/month free (then $0.0075/msg) |
| Blob Storage | Included in Storage | **$0.00** | Included in account cost |
| Table Storage | Included in Storage | **$0.00** | Included in account cost |
| **Total** | | **~$0.65/month** | Covered by $100 Azure for Students credit |

## Per-Order Cost Breakdown

Assuming 100 orders per class:

| Operation | Quantity | Unit Cost | Total |
|---|---|---|---|
| Function executions | ~10 per order × 100 = 1000 | $0.00 (free tier) | $0.00 |
| Storage writes | ~10 KB per order × 100 = 1 MB | $0.0002/GB | $0.00 |
| Cosmos DB RUs | ~10 RU per order × 100 = 1000 RU | $0.00 (free tier) | $0.00 |
| Event Grid operations | 2 per order (publish + deliver) × 100 = 200 | $0.60/million | $0.00012 |
| SMS | 1 per order (first 200 free) | $0.00 (free tier) | $0.00 |
| **Total per class** | | | **~$0.00012** |

## Free Tier Limits

| Resource | Limit | Classroom Equivalent |
|---|---|---|
| Function executions | 1M/month | ~100K classes of 100 orders |
| Cosmos DB RU/s | 1000 RU/s (free), or 400 RU/s (manual) | 40 concurrent orders |
| Cosmos DB storage | 25 GB | ~25M order documents |
| App Insights ingestion | 5 GB/month | ~5M function executions' logs |
| Event Grid ops | 100K/month (in free tier) | ~50K orders |
| ACS SMS | 200/month | 200 order confirmations |
| Storage transactions | 20K/month (free) | ~20K blob operations |

## When Will You Exceed Free Tier?

- **Functions**: >1M req/month = >30K/day
- **Cosmos DB**: >1000 RU/s sustained (complex queries)
- **App Insights**: >5 GB/month = >170 MB/day
- **SMS**: >200/month = after that $0.0075/msg (~$1.50 for 200 more)
- **Event Grid**: >100K ops/month = very unlikely for classroom

## Cost Optimization Tips

1. **Develop locally** with Azurite + Cosmos DB Emulator — $0.00 in Azure costs
2. **Deploy only** for final testing and live demos
3. **Delete resource group** (`az group delete`) when not in use
4. **Set budget alerts** at $10/month in Azure Cost Management
5. **Use Consumption plan** (not Premium or Dedicated)
6. **Cosmos DB Serverless** instead of provisioned — pay only for consumed RUs

## Comparison: Real World vs Classroom

| Aspect | Classroom (Azure for Students) | Production |
|---|---|---|
| Cosmos DB | Free Tier (1000 RU/s) | Multi-region, autoscale ($$$) |
| Functions | Consumption (Y1) | Premium (always warm) |
| App Insights | 5 GB ingestion | Unlimited (pay per GB) |
| ACS SMS | 200 free/month | $0.0075/msg bulk |
| Event Grid | 100K ops/month | Millions (negotiated) |
| **Monthly cost** | **~$0.65** | **$500-5000+** |
