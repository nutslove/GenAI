def extract_alert_info(alert_data: dict):
    status = alert_data.get("status", "unknown")
    labels = alert_data.get("labels", {})
    annotations = alert_data.get("annotations", {})
    starts_at = alert_data.get("startsAt", "")
    ends_at = alert_data.get("endsAt", "")
    generator_url = alert_data.get("generatorURL", "")

    alert_info = {
        "status": status,
        "labels": labels,
        "annotations": annotations,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "generator_url": generator_url
    }
    # print(f"Extracted Alert Info: {alert_info}")
    return alert_info