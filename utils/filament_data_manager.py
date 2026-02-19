import json
import os
import asyncio
from datetime import datetime

class FilamentDataManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.inventory_file = os.path.join(data_path, "inventory.json")
        self.logs_file = os.path.join(data_path, "logs.json")
        self.inventory = self.load_json(self.inventory_file)
        self.logs = self.load_json(self.logs_file)

    def load_json(self, filename):
        if not os.path.exists(filename):
            return []
        
        try:
            with open(filename, 'r') as f:
                content = f.read()
                if not content.strip(): 
                    return []
                return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            print(f"JSON_LOAD_ERROR: {filename} - {e}")
            return []
        return []

    def save_json(self, filename, data):
        tmp_filename = f"{filename}.tmp"
        try:
            with open(tmp_filename, 'w') as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_filename, filename)
        except Exception as e:
            print(f"Error saving {filename}: {e}")

    def get_inventory(self):
        # Reload to ensure fresh data
        self.inventory = self.load_json(self.inventory_file)
        return self.inventory

    def get_logs(self):
         # Reload to ensure fresh data
        self.logs = self.load_json(self.logs_file)
        return self.logs

    def update_filament_weight(self, filament_id, amount_used):
        """Reduces the weight of a filament by amount_used."""
        self.inventory = self.load_json(self.inventory_file) # Ensure fresh data before update
        for item in self.inventory:
            if item['id'] == filament_id:
                item['weight_g'] = round(max(0, item['weight_g'] - amount_used), 2)
                self.save_json(self.inventory_file, self.inventory)
                return True
        return False

    def add_inventory_item(self, type_name, brand, color, weight):
        """Adds a new filament reel to inventory."""
        self.inventory = self.load_json(self.inventory_file) # Ensure fresh
        new_id = 1
        if self.inventory:
            new_id = max(item['id'] for item in self.inventory) + 1
        
        new_item = {
            "id": new_id,
            "type": type_name,
            "brand": brand,
            "color": color,
            "weight_g": round(weight, 2)
        }
        self.inventory.append(new_item)
        self.save_json(self.inventory_file, self.inventory)
        return new_id

    def update_inventory_item(self, item_id, **kwargs):
        """Updates an existing inventory item with new values."""
        self.inventory = self.load_json(self.inventory_file)
        for item in self.inventory:
            if item['id'] == item_id:
                for key, value in kwargs.items():
                    if key in item:
                        if key == 'weight_g':
                            item[key] = round(float(value), 2)
                        else:
                            item[key] = value
                self.save_json(self.inventory_file, self.inventory)
                return True
        return False

    def log_usage(self, user_name, filament_id, amount_used):
        """Records a usage event."""
        # Find filament details for the log
        self.inventory = self.load_json(self.inventory_file)
        filament_details = next((item for item in self.inventory if item['id'] == filament_id), None)
        filament_str = f"{filament_details['color']} {filament_details['type']}" if filament_details else "Unknown"

        log_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user_name,
            "filament_id": filament_id,
            "filament_desc": filament_str,
            "amount_used": amount_used
        }
        
        self.logs = self.load_json(self.logs_file)
        self.logs.append(log_entry)
        self.save_json(self.logs_file, self.logs)

    def get_consumption_stats(self):
        """Calculates total usage for current Day, Week, and Month."""
        self.logs = self.load_json(self.logs_file) # Ensure fresh
        now = datetime.now()
        current_day = now.strftime("%Y-%m-%d")
        current_week = now.strftime("%Y-W%U")
        current_month = now.strftime("%Y-%m")

        stats = {
            "daily": 0.0,
            "weekly": 0.0,
            "monthly": 0.0
        }

        for log in self.logs:
            try:
                amt = float(log.get('amount_used', 0))
            except (ValueError, TypeError):
                continue

            ts_str = log.get('timestamp', '')
            try:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                
                day_key = dt.strftime("%Y-%m-%d")
                week_key = dt.strftime("%Y-W%U")
                month_key = dt.strftime("%Y-%m")

                if day_key == current_day:
                    stats["daily"] += amt
                
                if week_key == current_week:
                    stats["weekly"] += amt
                
                if month_key == current_month:
                    stats["monthly"] += amt

            except ValueError:
                pass
        
        # Round values for display
        for k in stats:
            stats[k] = round(stats[k], 2)
        
        return stats

    def export_logs_to_csv(self):
        """Converts logs to CSV string."""
        self.logs = self.load_json(self.logs_file)
        if not self.logs:
            return "No logs available."
        
        # CSV Header
        csv_content = "Timestamp,User,Filament,Amount Used (g)\n"
        
        for log in self.logs:
            ts = log.get('timestamp', '')
            user = log.get('user', 'Unknown')
            filament = log.get('filament_desc', 'Unknown')
            amount = log.get('amount_used', 0)
            
            # Simple manual CSV formatting to avoid imports if possible, 
            # but wrapping in quotes handles commas in names
            csv_content += f'"{ts}","{user}","{filament}",{amount}\n'
            
        return csv_content
