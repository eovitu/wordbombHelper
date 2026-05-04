import threading

from shared.parsing import to_float, to_int


class AutoplayStateService:
    def __init__(self):
        self.config = {
            "lang": "Português",
            "min_len": 1,
            "max_len": 46,
            "strategy": "random",
            "wpm": 150,
            "error_rate": 0.0,
            "hesitation_prob": 0.05,
            "retry_rate": 0.0,
            "late_error_rate": 0.0,
            "max_typos": 2,
            "max_late_errors": 1,
            "priority_min_len": 1,
            "priority_max_len": 46,
            "priority_letters": "",
            "exclude_letters": "",
            "starts_with_letters": "",
            "finish_with_letters": "",
            "recover_target": 2,
            "recover_exclude": "",
            "priority_sublist": "",
            "delayed_type": False,
            "add_period_prob": 0.0,
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
            if "lang" in data:
                self.config["lang"] = data["lang"]
            if "min_len" in data:
                self.config["min_len"] = to_int(data["min_len"], self.config["min_len"])
            if "max_len" in data:
                self.config["max_len"] = to_int(data["max_len"], self.config["max_len"])
            if "strategy" in data:
                self.config["strategy"] = data["strategy"]
            if "wpm" in data:
                self.config["wpm"] = to_int(data["wpm"], self.config["wpm"])
            if "error_rate" in data:
                self.config["error_rate"] = to_float(data["error_rate"], self.config["error_rate"])
            if "hesitation_prob" in data:
                self.config["hesitation_prob"] = to_float(data["hesitation_prob"], self.config["hesitation_prob"])
            if "retry_rate" in data:
                self.config["retry_rate"] = to_float(data["retry_rate"], self.config["retry_rate"])
            if "late_error_rate" in data:
                self.config["late_error_rate"] = to_float(data["late_error_rate"], self.config["late_error_rate"])
            if "max_typos" in data:
                self.config["max_typos"] = to_int(data["max_typos"], self.config["max_typos"])
            if "max_late_errors" in data:
                self.config["max_late_errors"] = to_int(data["max_late_errors"], self.config["max_late_errors"])
            if "priority_min_len" in data:
                self.config["priority_min_len"] = to_int(data["priority_min_len"], self.config["priority_min_len"])
            if "priority_max_len" in data:
                self.config["priority_max_len"] = to_int(data["priority_max_len"], self.config["priority_max_len"])
            if "priority_letters" in data:
                self.config["priority_letters"] = data["priority_letters"]
            if "exclude_letters" in data:
                self.config["exclude_letters"] = data["exclude_letters"]
            if "starts_with_letters" in data:
                self.config["starts_with_letters"] = data["starts_with_letters"]
            if "finish_with_letters" in data:
                self.config["finish_with_letters"] = data["finish_with_letters"]
            if "recover_target" in data:
                self.config["recover_target"] = to_int(data["recover_target"], self.config["recover_target"])
            if "recover_exclude" in data:
                self.config["recover_exclude"] = data["recover_exclude"]
            if "priority_sublist" in data:
                self.config["priority_sublist"] = data["priority_sublist"]
            if "delayed_type" in data:
                self.config["delayed_type"] = bool(data["delayed_type"])
            if "add_period_prob" in data:
                self.config["add_period_prob"] = to_float(data["add_period_prob"], self.config["add_period_prob"])
            if "auto_type" in data:
                self.config["auto_type"] = bool(data["auto_type"])

            return dict(self.config)
