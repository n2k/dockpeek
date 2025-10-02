export const state = {
  allContainersData: [],
  allServersData: [],
  filteredAndSortedContainers: [],
  swarmServers: [],
  currentSortColumn: "name",
  currentSortDirection: "asc",
  currentServerFilter: "all",
  isDataLoaded: false,
  isCheckingForUpdates: false,
  updateCheckController: null,
  columnOrder: ['name', 'stack', 'server', 'ports', 'traefik', 'image', 'tags', 'status'],
  columnVisibility: {
    name: true,
    server: true,
    stack: true,
    image: true,
    tags: true,
    status: true,
    ports: true,
    traefik: true
  }
};
