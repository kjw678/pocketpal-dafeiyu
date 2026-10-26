import {assertOfficialCloudAvailable} from '../config/cloud';

// Compatibility boundary for existing callers. No Firebase SDK is loaded and
// no App Check token is fabricated in the independent Dafeiyu application.
export const initializeAppCheck = async (): Promise<void> => {
  assertOfficialCloudAvailable();
};

export const getAppCheckToken = async (): Promise<string> => {
  assertOfficialCloudAvailable();
  throw new Error('No Firebase App Check provider is installed.');
};
