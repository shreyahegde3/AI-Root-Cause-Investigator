import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.graph import run_investigation
from app.utils.logger import logger

def test_workflow_conversion():
    print("\n=== LANGGRAPH TEST 1: February Conversion Drop Workflow ===")
    question = "Why did conversion drop in February?"
    try:
        report = run_investigation(question)
        print("\nFinal Report Output:")
        print(f"Summary: {report['summary']}")
        print(f"Confidence: {report['confidence'] * 100:.1f}%")
        print(f"Contributors: {report['contributors']}")
        print(f"Recommendations: {report['recommendations']}")
        
        # Schema assertions
        assert "summary" in report, "Report missing summary!"
        assert "contributors" in report, "Report missing contributors!"
        assert "confidence" in report, "Report missing confidence score!"
        assert "recommendations" in report, "Report missing recommendations!"
        assert len(report["recommendations"]) > 0, "No business recommendations generated!"
        
        print("\nSuccess: LangGraph February Conversion drop pipeline passed.")
    except Exception as e:
        print(f"\nPipeline Execution Failed: {e}")
        sys.exit(1)

def test_workflow_bangalore():
    print("\n=== LANGGRAPH TEST 2: April Bangalore Electronics Drop Workflow ===")
    question = "Why did revenue decrease in Bangalore during late April?"
    try:
        report = run_investigation(question)
        print("\nFinal Report Output:")
        print(f"Summary: {report['summary']}")
        print(f"Confidence: {report['confidence'] * 100:.1f}%")
        print(f"Contributors: {report['contributors']}")
        print(f"Recommendations: {report['recommendations']}")
        
        assert "summary" in report, "Report missing summary!"
        assert len(report["contributors"]) > 0, "No contributors identified for April revenue drop!"
        
        print("\nSuccess: LangGraph Bangalore Electronics drop pipeline passed.")
    except Exception as e:
        print(f"\nPipeline Execution Failed: {e}")
        sys.exit(1)

def main():
    print("Starting LangGraph Agent Workflow validation tests...")
    test_workflow_conversion()
    test_workflow_bangalore()
    print("\nAll LangGraph Agent pipeline checks passed successfully!")

if __name__ == "__main__":
    main()
