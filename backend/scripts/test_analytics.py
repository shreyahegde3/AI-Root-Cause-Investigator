import os
import sys
from datetime import date

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.connection import SessionLocal
from app.services.analytics import AnalyticsService

def test_conversion_anomaly(db):
    print("\n--- TEST 1: February 2026 Conversion Rate Drop ---")
    p1_start, p1_end = date(2026, 1, 1), date(2026, 1, 31)
    p2_start, p2_end = date(2026, 2, 1), date(2026, 2, 28)
    
    report = AnalyticsService.compare_periods(
        db=db,
        metric="conversion_rate",
        p1_start=p1_start,
        p1_end=p1_end,
        p2_start=p2_start,
        p2_end=p2_end,
        filters={}
    )
    
    print(f"Jan 2026 CR: {report['period_1']['value']:.3f}%")
    print(f"Feb 2026 CR: {report['period_2']['value']:.3f}%")
    print(f"CR Drop: {report['percentage_change']:.2f}% (Relative change)")
    print(f"CR Absolute Diff: {report['absolute_change']:.3f}% points")
    
    # Assert drop is in expected range (~35%)
    assert report['percentage_change'] < -30.0, "February conversion drop not detected correctly!"
    print("Success: February Conversion drop detected successfully.")

def test_bangalore_anomaly(db):
    print("\n--- TEST 2: April 2026 Bangalore Electronics Drop ---")
    # Comparing April second half (anomaly) vs April first half (normal) in Bangalore
    p1_start, p1_end = date(2026, 4, 1), date(2026, 4, 14)
    p2_start, p2_end = date(2026, 4, 15), date(2026, 4, 30)
    
    report = AnalyticsService.compare_periods(
        db=db,
        metric="revenue",
        p1_start=p1_start,
        p1_end=p1_end,
        p2_start=p2_start,
        p2_end=p2_end,
        filters={"city": "Bangalore", "category": "Electronics"}
    )
    
    v1 = report['period_1']['value']
    v2 = report['period_2']['value']
    pct_change = report['percentage_change']
    
    print(f"Bangalore Electronics Revenue April 1-14: ${v1:,.2f}")
    print(f"Bangalore Electronics Revenue April 15-30: ${v2:,.2f}")
    print(f"Revenue Change: {pct_change:+.2f}%")
    
    assert pct_change < -70.0, "Bangalore Electronics drop not detected correctly!"
    print("Success: Bangalore Electronics drop detected successfully.")

def test_corporate_anomaly(db):
    print("\n--- TEST 3: October 2025 Corporate Office Supplies Drop ---")
    p1_start, p1_end = date(2025, 9, 1), date(2025, 9, 30)
    p2_start, p2_end = date(2025, 10, 1), date(2025, 10, 31)
    
    report = AnalyticsService.compare_periods(
        db=db,
        metric="orders",
        p1_start=p1_start,
        p1_end=p1_end,
        p2_start=p2_start,
        p2_end=p2_end,
        filters={"segment": "Corporate", "category": "Office Supplies"}
    )
    
    v1 = report['period_1']['value']
    v2 = report['period_2']['value']
    pct_change = report['percentage_change']
    
    print(f"Corporate Office Supplies Orders Sept 2025: {v1}")
    print(f"Corporate Office Supplies Orders Oct 2025: {v2}")
    print(f"Order Volume Change: {pct_change:+.2f}%")
    
    assert pct_change < -60.0, "Corporate Office Supplies drop not detected correctly!"
    print("Success: Corporate Office Supplies drop detected successfully.")

def main():
    print("Starting Analytics Engine verification tests...")
    db = SessionLocal()
    try:
        test_conversion_anomaly(db)
        test_bangalore_anomaly(db)
        test_corporate_anomaly(db)
        print("\nAll Analytics Engine mathematical checks passed!")
    except AssertionError as e:
        print(f"\nAssertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nExecution Error: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
