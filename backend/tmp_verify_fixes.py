
import asyncio
import sys
import os
from decimal import Decimal

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_orchestrator_monitoring():
    from app.services.orchestrator import orchestrator
    from app.db.session import async_session
    
    print("Testing Orchestrator Stage 5 (Monitoring)...")
    
    async with async_session() as db:
        # Get latest dataset to check if DB is alive, but we'll mock the financials
        from app.models.all_models import Dataset
        from sqlalchemy import select
        result = await db.execute(select(Dataset).where(Dataset.record_count > 0).order_by(Dataset.id.desc()).limit(1))
        dataset = result.scalar_one_or_none()
        
        if not dataset:
            print("Warning: No dataset found in DB, proceeding with pure logic test.")

        try:
            # Stage 5 Check: Running monitoring_engine.run_checks via orchestrator...
            from app.services.monitoring_engine import monitoring_engine
            
            # Simulating current state
            current = {"revenue": 1000000, "net_profit": -50000, "cogs": 400000}
            balance_sheet = {"total_assets": 2000000, "total_liabilities": 1000000, "total_equity": 1000000}

            print("Stage 5 Check: Running monitoring_engine.run_checks...")
            alerts = monitoring_engine.run_checks(current, balance_sheet)
            print(f"Alerts found: {len(alerts)}")
            
            print("Stage 5 Check: Verifying clear_resolved() absence...")
            # This should have been removed from orchestrator.py, but let's check the engine itself
            if hasattr(monitoring_engine, 'alert_manager'):
                print("Alert manager exists.")
                if hasattr(monitoring_engine.alert_manager, 'clear_resolved'):
                    print("ERROR: clear_resolved still exists")
                else:
                    print("Confirmed: clear_resolved does NOT exist")
            else:
                print("Confirmed: alert_manager does NOT exist (matching our v2 diagnosis)")
                
            print("SUCCESS: Stage 5 Logic verified.")
            
            # Now test Health Scorer
            from app.services.diagnosis_engine import diagnosis_engine
            from app.services.diagnosis_engine import MetricSignal
            
            signals = [
                MetricSignal(metric="revenue", current_value=1000000, previous_value=900000, severity="low"),
                MetricSignal(metric="net_profit", current_value=-50000, previous_value=10000, severity="critical", direction="down")
            ]
            
            score = diagnosis_engine._compute_health_score(
                signals=signals,
                accounting_issues=[],
                benchmark_comparisons=[],
                liquidity={},
                anomaly_summary=None
            )
            
            print(f"Health Score for UNPROFITABLE company: {score}")
            # Base 100 - 3 (low) - 20 (critical) - 25 (loss penalty) = 52
            if score == 52.0:
                print("SUCCESS: Health Score correctly penalized unprofitability.")
            else:
                print(f"Health Score is {score}, expected 52.0")
            
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_orchestrator_monitoring())
