from loguru import logger
import sys
from pathlib import Path


def setup_logger():
    ROOT_DIR = Path(__file__).resolve().parent.parent.parent
    log_dir = ROOT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sink=log_dir / "{time:YYYY-MM-DD}.log",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        level="DEBUG",
    )
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        level="DEBUG",
    )
    logger.add(
        sink=log_dir / "{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
        level="INFO",
    )


def get_logger(name: str = "backend"):
    return logger.bind(component=name)


setup_logger()
