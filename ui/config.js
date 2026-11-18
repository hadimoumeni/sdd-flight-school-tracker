// Base URLs of the two services. These are the local docker compose values;
// the CD pipeline overwrites this file with the deployed URLs.
window.APP_CONFIG = {
  maintenanceUrl: "http://localhost:8001",
  schedulingUrl: "http://localhost:8002",
};
