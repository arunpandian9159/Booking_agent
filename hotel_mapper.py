import pandas as pd
import ast
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class HotelMapper:
    """
    A class to map hotels by destination and package type using the all_hotels.csv data.
    """
    
    def __init__(self, csv_file_path: str = 'all_hotels.csv'):
        """
        Initialize the HotelMapper with the CSV file.
        
        Args:
            csv_file_path (str): Path to the all_hotels.csv file
        """
        self.csv_file_path = csv_file_path
        self.df = None
        self._load_data()
    
    def _load_data(self):
        """Load and parse the CSV data."""
        try:
            logger.info(f"Loading hotel data from {self.csv_file_path}")
            self.df = pd.read_csv(self.csv_file_path)
            logger.info(f"Loaded {len(self.df)} hotels from CSV")
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            self.df = pd.DataFrame()
    
    def get_hotels_by_destination(self, destination_id: str) -> List[Dict[str, Any]]:
        """
        Get all hotels for a specific destination ID.
        
        Args:
            destination_id (str): The destination ID to filter by
            
        Returns:
            List[Dict]: List of hotel objects with details
        """
        if self.df is None or self.df.empty:
            logger.warning("No hotel data available")
            return []
        
        hotels = []
        
        for _, row in self.df.iterrows():
            try:
                # Parse location data
                location_data = ast.literal_eval(row['location'])
                if location_data.get('destinationId') != destination_id:
                    continue
                
                # Parse room details
                room_details = ast.literal_eval(row['hotelRoomDetails'])
                
                hotel_info = {
                    'hotelName': row['hotelName'],
                    'hotelId': row['hotelId'],
                    'review': row['review'],
                    'viewPoint': row['viewPoint'],
                    'location': location_data,
                    'rooms': []
                }
                
                for room in room_details:
                    room_info = {
                        'roomType': room.get('hotelRoomType'),
                        'maxAdult': room.get('maxAdult'),
                        'maxChild': room.get('maxChild'),
                        'maxInf': room.get('maxInf'),
                        'roomCapacity': room.get('roomCapacity'),
                        'isAc': room.get('isAc'),
                        'mealPlans': []
                    }
                    
                    for meal in room.get('mealPlan', []):
                        meal_info = {
                            'mealPlan': meal.get('mealPlan'),
                            'roomPrice': meal.get('roomPrice'),
                            'adultPrice': meal.get('adultPrice'),
                            'childPrice': meal.get('childPrice'),
                            'seasonType': meal.get('seasonType'),
                            'startDate': meal.get('startDate', []),
                            'endDate': meal.get('endDate', [])
                        }
                        room_info['mealPlans'].append(meal_info)
                    
                    if room_info['mealPlans']:
                        hotel_info['rooms'].append(room_info)
                
                if hotel_info['rooms']:
                    hotels.append(hotel_info)
                    
            except Exception as e:
                logger.debug(f"Error parsing hotel row: {e}")
                continue
        
        logger.info(f"Found {len(hotels)} hotels for destination {destination_id}")
        return hotels
    
    def get_hotels_by_destination_and_package(self, 
                                            destination_id: str, 
                                            package_type: Optional[str] = None,
                                            room_type: Optional[str] = None,
                                            season_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get hotels filtered by destination ID and optionally by package type, room type, and season.
        
        Args:
            destination_id (str): The destination ID to filter by
            package_type (str, optional): Package type filter (e.g., 'cp', 'map')
            room_type (str, optional): Room type filter (e.g., 'Deluxe', 'Luxury Room')
            season_type (str, optional): Season type filter (e.g., 'peakSeason', 'offSeason')
            
        Returns:
            List[Dict]: List of filtered hotel objects
        """
        hotels = self.get_hotels_by_destination(destination_id)
        
        if not hotels:
            return []
        
        filtered_hotels = []
        
        for hotel in hotels:
            filtered_hotel = {
                'hotelName': hotel['hotelName'],
                'hotelId': hotel['hotelId'],
                'review': hotel['review'],
                'viewPoint': hotel['viewPoint'],
                'location': hotel['location'],
                'rooms': []
            }
            
            for room in hotel['rooms']:
                # Filter by room type if specified
                if room_type and room['roomType'] != room_type:
                    continue
                
                filtered_room = {
                    'roomType': room['roomType'],
                    'maxAdult': room['maxAdult'],
                    'maxChild': room['maxChild'],
                    'maxInf': room['maxInf'],
                    'roomCapacity': room['roomCapacity'],
                    'isAc': room['isAc'],
                    'mealPlans': []
                }
                
                for meal in room['mealPlans']:
                    # Filter by package type if specified
                    if package_type and meal['mealPlan'] != package_type:
                        continue
                    
                    # Filter by season type if specified
                    if season_type and meal['seasonType'] != season_type:
                        continue
                    
                    filtered_room['mealPlans'].append(meal)
                
                if filtered_room['mealPlans']:
                    filtered_hotel['rooms'].append(filtered_room)
            
            if filtered_hotel['rooms']:
                filtered_hotels.append(filtered_hotel)
        
        logger.info(f"Filtered to {len(filtered_hotels)} hotels for destination {destination_id}, "
                   f"package_type={package_type}, room_type={room_type}, season_type={season_type}")
        return filtered_hotels
    
    def get_hotel_summary_by_destination(self, destination_id: str) -> Dict[str, Any]:
        """
        Get a summary of hotels for a destination including price ranges and available packages.
        
        Args:
            destination_id (str): The destination ID
            
        Returns:
            Dict: Summary information about hotels in the destination
        """
        hotels = self.get_hotels_by_destination(destination_id)
        
        if not hotels:
            return {
                'destination_id': destination_id,
                'total_hotels': 0,
                'price_range': {'min': 0, 'max': 0, 'average': 0},
                'available_packages': [],
                'available_room_types': [],
                'hotels': []
            }
        
        all_prices = []
        package_types = set()
        room_types = set()
        
        for hotel in hotels:
            for room in hotel['rooms']:
                room_types.add(room['roomType'])
                for meal in room['mealPlans']:
                    package_types.add(meal['mealPlan'])
                    if meal['roomPrice'] and isinstance(meal['roomPrice'], (int, float)):
                        all_prices.append(meal['roomPrice'])
        
        summary = {
            'destination_id': destination_id,
            'total_hotels': len(hotels),
            'price_range': {
                'min': min(all_prices) if all_prices else 0,
                'max': max(all_prices) if all_prices else 0,
                'average': sum(all_prices) / len(all_prices) if all_prices else 0
            },
            'available_packages': list(package_types),
            'available_room_types': list(room_types),
            'hotels': [{'name': h['hotelName'], 'id': h['hotelId'], 'review': h['review']} for h in hotels]
        }
        
        return summary
    
    def get_available_destinations(self) -> List[str]:
        """
        Get list of all available destination IDs.
        
        Returns:
            List[str]: List of destination IDs
        """
        if self.df is None or self.df.empty:
            return []
        
        destination_ids = set()
        
        for _, row in self.df.iterrows():
            try:
                location_data = ast.literal_eval(row['location'])
                dest_id = location_data.get('destinationId')
                if dest_id:
                    destination_ids.add(dest_id)
            except:
                continue
        
        return list(destination_ids)
    
    def search_hotels_by_name(self, hotel_name: str, destination_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search hotels by name, optionally filtered by destination.
        
        Args:
            hotel_name (str): Hotel name to search for
            destination_id (str, optional): Optional destination filter
            
        Returns:
            List[Dict]: List of matching hotels
        """
        if self.df is None or self.df.empty:
            return []
        
        matching_hotels = []
        hotel_name_lower = hotel_name.lower()
        
        for _, row in self.df.iterrows():
            try:
                # Check destination filter
                if destination_id:
                    location_data = ast.literal_eval(row['location'])
                    if location_data.get('destinationId') != destination_id:
                        continue
                
                # Check hotel name
                if hotel_name_lower not in row['hotelName'].lower():
                    continue
                
                # Parse room details
                room_details = ast.literal_eval(row['hotelRoomDetails'])
                
                hotel_info = {
                    'hotelName': row['hotelName'],
                    'hotelId': row['hotelId'],
                    'review': row['review'],
                    'viewPoint': row['viewPoint'],
                    'location': ast.literal_eval(row['location']),
                    'rooms': []
                }
                
                for room in room_details:
                    room_info = {
                        'roomType': room.get('hotelRoomType'),
                        'mealPlans': []
                    }
                    
                    for meal in room.get('mealPlan', []):
                        meal_info = {
                            'mealPlan': meal.get('mealPlan'),
                            'roomPrice': meal.get('roomPrice'),
                            'adultPrice': meal.get('adultPrice'),
                            'childPrice': meal.get('childPrice'),
                            'seasonType': meal.get('seasonType')
                        }
                        room_info['mealPlans'].append(meal_info)
                    
                    if room_info['mealPlans']:
                        hotel_info['rooms'].append(room_info)
                
                if hotel_info['rooms']:
                    matching_hotels.append(hotel_info)
                    
            except Exception as e:
                logger.debug(f"Error parsing hotel row: {e}")
                continue
        
        return matching_hotels

# Global instance for easy access
_hotel_mapper_instance = None

def get_hotel_mapper() -> HotelMapper:
    """Get the global hotel mapper instance."""
    global _hotel_mapper_instance
    if _hotel_mapper_instance is None:
        _hotel_mapper_instance = HotelMapper()
    return _hotel_mapper_instance

def map_hotels_by_destination_and_package(destination_id: str, 
                                        package_type: Optional[str] = None,
                                        room_type: Optional[str] = None,
                                        season_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to map hotels by destination and package.
    
    Args:
        destination_id (str): The destination ID to filter by
        package_type (str, optional): Package type filter (e.g., 'cp', 'map')
        room_type (str, optional): Room type filter
        season_type (str, optional): Season type filter
        
    Returns:
        List[Dict]: List of filtered hotel objects
    """
    mapper = get_hotel_mapper()
    return mapper.get_hotels_by_destination_and_package(
        destination_id, package_type, room_type, season_type
    ) 