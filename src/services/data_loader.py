# Backward compatibility — DataLoader is now part of DataService
from src.services.data_manager import DataService as DataLoader, DataService

__all__ = ["DataLoader", "DataService"]
