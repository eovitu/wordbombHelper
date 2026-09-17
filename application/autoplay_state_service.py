"""Estado thread-safe do auto-play: config e log ring-buffer."""
import threading

from shared.parsing import to_bool, to_int


class AutoplayStateService:
    def __init__(self):
        self.config = {
            "lang": "Português",
            "min_len": 1,
            "max_len": 46,
            "strategy": "random",
            "priority_min_len": 1,
            "priority_max_len": 46,
            "priority_letters": "",
            "exclude_letters": "",
            "starts_with_letters": "",
            "finish_with_letters": "",
            "recover_target": 2,
            "recover_exclude": "",
            "recover_mode": "casual",
            "priority_sublist": "",
            "auto_type": False,
        }
        self.logs = []
        self.log_seq = 0
        self.config_lock = threading.Lock()
        self.logs_lock = threading.Lock()

    def snapshot_config(self):
        with self.config_lock:
            return dict(self.config)

    def add_log(self, msg):
        with self.logs_lock:
            self.log_seq += 1
            self.logs.append({"id": self.log_seq, "msg": msg})
            if len(self.logs) > 50:
                self.logs.pop(0)

    def last_logs(self, count=10):
        with self.logs_lock:
            return list(self.logs[-count:])

    def update_from_payload(self, data):
        with self.config_lock:
            for key in ("lang", "strategy", "priority_letters", "exclude_letters",
                        "starts_with_letters", "finish_with_letters", "recover_exclude", "priority_sublist"):
                if key in data:
                    self.config[key] = data[key]
            if data.get("recover_mode") in ("casual", "ranked"):
                self.config["recover_mode"] = data["recover_mode"]
            for key in ("min_len", "max_len", "priority_min_len", "priority_max_len", "recover_target"):
                if key in data:
                    self.config[key] = to_int(data[key], self.config[key])
            if "auto_type" in data:
                self.config["auto_type"] = to_bool(data["auto_type"], self.config["auto_type"])
            return dict(self.config)
