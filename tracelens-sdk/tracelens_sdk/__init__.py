from .client import TraceLens, TraceRun, TraceStep
from .events import TraceEvent

__version__ = "0.3.0"
__all__ = ["TraceLens", "TraceRun", "TraceStep", "TraceEvent"]

def langchain_callback(*args, **kwargs):
    """Create a LangChain callback handler (requires the ``langchain`` extra)."""
    from .integrations import TraceLensCallbackHandler
    return TraceLensCallbackHandler(*args, **kwargs)

__all__.append("langchain_callback")
