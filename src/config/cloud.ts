// Dafeiyu has no identity or authorization for PocketPal's official cloud.
// This policy does not restrict user-configured servers, web tools or memory.
export const officialCloudEnabled = false;

export const assertOfficialCloudAvailable = (): void => {
  if (!officialCloudEnabled) {
    throw new Error(
      'PocketPal cloud submission is unavailable in Dafeiyu. Local results remain on this device.',
    );
  }
};
