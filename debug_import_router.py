try:
    from src.graph.workflow import route_from_supervisor
    print("Import successful")
except Exception as e:
    import traceback
    traceback.print_exc()
