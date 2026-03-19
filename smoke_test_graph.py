
import os
import sys
from unittest.mock import MagicMock, patch

# Add the current directory to sys.path so we can import tradingagents
sys.path.append(os.getcwd())

def smoke_test():
    print("Starting smoke test: Compiling TradingAgentsGraph...")
    
    # Set up basic environment/config
    config = {
        "project_dir": ".",
        "llm_provider": "openai",
        "quick_think_llm": "gpt-4o-mini",
        "deep_think_llm": "o1-mini",
    }
    
    try:
        # Mock create_llm_client before importing TradingAgentsGraph if possible, 
        # but better to patch it where it is used.
        with patch("tradingagents.graph.trading_graph.create_llm_client") as mock_create:
            mock_client = MagicMock()
            mock_client.get_llm.return_value = MagicMock()
            mock_create.return_value = mock_client
            
            from tradingagents.graph.trading_graph import TradingAgentsGraph
            
            # Instantiate the graph. This will trigger GraphSetup.setup_graph() and workflow.compile()
            graph = TradingAgentsGraph(debug=True, config=config)
            print("Successfully compiled TradingAgentsGraph!")
            
    except Exception as e:
        print(f"Failed to compile TradingAgentsGraph: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    smoke_test()
