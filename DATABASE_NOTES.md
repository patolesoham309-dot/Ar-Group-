# Data model overview

- users: username, password hash, role, fixed_bus_id
- buses: bus_number
- routes: route_name
- diesel_entries: date, driver, bus, route, meter KM, litres, rate, full_tank flag,
  meter photo, pump photo, approval status, reviewer

Future tables recommended:
- trips: trip start/end meter, route, actual fuel consumed, trip-level average
- driver_bus_assignments: dated assignment history for rotation
- audit_logs: who changed what and when
- app_settings: fuel price defaults, alert thresholds
