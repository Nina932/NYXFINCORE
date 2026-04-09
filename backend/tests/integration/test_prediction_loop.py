import sys
import os
import asyncio
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.database import AsyncSessionLocal
from app.models.all_models import Dataset, RevenueItem, COGSItem, GAExpenseItem, PredictionRecord, PredictionOutcome
from app.services.scheduler import ReportScheduler
from sqlalchemy import select

async def create_complex_dataset(db) -> int:
    """Create a dataset with complex nested naming to test dynamic fuzzy resolution."""
    print("🚀 Creating complex financial dataset...")
    
    # 1. Create dataset
    ds = Dataset(name="Automated Complex Test Dataset - Mar 2026", period="March 2026", is_active=True, record_count=0)
    db.add(ds)
    await db.flush()
    ds_id = ds.id
    
    # Disable previously active datasets temporarily internally if needed
    
    # 2. Add Revenue
    # Real world names with noise
    db.add(RevenueItem(dataset_id=ds_id, product="Premium Unleaded 95 (B2B Bulk)", segment="B2B Wholesale EU", net=8_500_000))
    db.add(RevenueItem(dataset_id=ds_id, product="Standard Retail Diesel V2", segment="Retail Local Ops", net=12_250_000))
    db.add(RevenueItem(dataset_id=ds_id, product="Bitumen Industrial Grade 60/70", segment="Wholesale Heavy", net=4_100_000))
    
    # 3. Add COGS
    db.add(COGSItem(dataset_id=ds_id, product="Premium Unleaded 95 (B2B Bulk)", segment="B2B Wholesale EU", total_cogs=7_900_000))
    db.add(COGSItem(dataset_id=ds_id, product="Standard Retail Diesel V2", segment="Retail Local Ops", total_cogs=10_100_000))
    db.add(COGSItem(dataset_id=ds_id, product="Bitumen Industrial Grade 60/70", segment="Wholesale Heavy", total_cogs=3_850_000))
    
    # 4. Add GA
    db.add(GAExpenseItem(dataset_id=ds_id, account_code="7310.LOCAL. MARKETING", account_name="Regional Ad Spend", amount=500_000))
    db.add(GAExpenseItem(dataset_id=ds_id, account_code="7410.HQ.DEPRC", account_name="HQ Depreciation & Amortization", amount=1_200_000))
    
    await db.commit()
    return ds_id

async def test_dynamic_prediction_resolution():
    async with AsyncSessionLocal() as db:
        # Step 0: Deactivate any current active dataset so our test is isolated
        await db.execute(select(Dataset).where(Dataset.is_active == True))
        active_datasets = (await db.execute(select(Dataset).where(Dataset.is_active == True))).scalars().all()
        for ad in active_datasets:
            ad.is_active = False
        await db.commit()

        # Step 1: Create dataset
        ds_id = await create_complex_dataset(db)
        print(f"✅ Created Dataset ID: {ds_id} and set to ACTIVE.")
        
        # Step 2: Seed predictions
        print("\n🚀 Injecting dynamically named predictions (Unresolved)...")
        predictions = [
            # Exact metric match
            PredictionRecord(prediction_type="metric", metric="gross profit", predicted_value=2_500_000, source_method="auto_test", resolved=False),
            # Dynamic Revenue by Product match
            PredictionRecord(prediction_type="metric", metric="Unleaded 95", predicted_value=8_000_000, source_method="auto_test", resolved=False),
            # Dynamic Revenue by Segment match
            PredictionRecord(prediction_type="metric", metric="Retail Local Ops", predicted_value=12_000_000, source_method="auto_test", resolved=False),
            # Dynamic GA Expense match
            PredictionRecord(prediction_type="metric", metric="marketing", predicted_value=450_000, source_method="auto_test", resolved=False),
            # Misses completely
            PredictionRecord(prediction_type="metric", metric="flying cars segment", predicted_value=1_000, source_method="auto_test", resolved=False)
        ]
        db.add_all(predictions)
        await db.commit()

        for p in predictions:
            print(f"   [P_ID: {p.id}] Metric: '{p.metric}' (Predicted: {p.predicted_value:,.2f})")

        # Step 3: Run the new _resolve_open_predictions loop
        print("\n⚙️ Running ReportScheduler._resolve_open_predictions...")
        scheduler = ReportScheduler()
        await scheduler._resolve_open_predictions(db)
        
        # Step 4: Verify Outcomes
        print("\n📊 Verification Results:")
        for p in predictions:
            await db.refresh(p)
            q = select(PredictionOutcome).where(PredictionOutcome.prediction_id == p.id)
            outcome = (await db.execute(q)).scalar_one_or_none()
            
            if outcome:
                print(f"✅ Resolved! Metric: '{p.metric}' -> Actual matched: {outcome.actual_value:,.2f} | Error: {outcome.error_pct}%")
            else:
                print(f"❌ NOT Resolved. Metric: '{p.metric}'")

        # Step 5: Cleanup (Reset active state)
        print("\n🧹 Cleaning up test data...")
        for p in predictions:
            db.delete(p)
            q = select(PredictionOutcome).where(PredictionOutcome.prediction_id == p.id)
            for o in (await db.execute(q)).scalars():
                db.delete(o)
        
        test_ds = await db.get(Dataset, ds_id)
        if test_ds: test_ds.is_active = False
        
        for ad in active_datasets:
            ad.is_active = True
            
        await db.commit()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_dynamic_prediction_resolution())
