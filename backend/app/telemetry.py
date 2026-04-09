"""
telemetry.py -- OpenTelemetry Setup for NYX Core FinAI
"""

import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from app.config import settings

logger = logging.getLogger("finai.telemetry")

def setup_telemetry(engine=None):
    """Initializes OpenTelemetry export and tracing components.
    
    Args:
        engine: Optional SQLAlchemy engine to instrument.
    """
    
    # Check if tracing is actually requested
    if getattr(settings, "OTEL_MODE", "disabled").lower() == "disabled":
        logger.info("OpenTelemetry is disabled via OTEL_MODE.")
        return
        
    logger.info(f"Initializing OpenTelemetry in '{settings.OTEL_MODE}' mode...")

    # 1. Provide Context/Resource for traces
    resource = Resource.create({
        "service.name": settings.APP_NAME.replace(" ", "_"),
        "service.version": settings.APP_VERSION,
        "deployment.environment": settings.APP_ENV,
        "telemetry.sdk.language": "python",
        "telemetry.sdk.name": "opentelemetry",
        "company.name": settings.COMPANY_NAME
    })

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # 2. Select Exporter
    if settings.OTEL_MODE.lower() == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            # Using standard Jaeger local destination 4317
            exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
            logger.info("Using OTLPSpanExporter targeting localhost:4317")
        except ImportError:
            logger.warning("otlp exporter not installed. Falling back to Console.")
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()
    else:
        # Default to Console
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        exporter = ConsoleSpanExporter()
        logger.info("Using ConsoleSpanExporter")

    # 3. Add to processor pipeline
    provider.add_span_processor(BatchSpanProcessor(exporter))
    
    # 4. Instrument SQLAlchemy if engine provided
    if engine:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumentation complete.")
        except Exception as e:
            logger.warning(f"SQLAlchemy instrumentation failed: {e}")

    # 5. Global Instrumentation (HTTPX)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation complete.")
    except Exception as e:
        logger.warning(f"HTTPX instrumentation failed: {e}")
    
    logger.info("OpenTelemetry configuration complete.")
