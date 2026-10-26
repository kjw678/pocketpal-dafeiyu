jest.mock('@env', () => ({APP_URL: 'dafeiyu://app'}));
jest.mock('@supabase/supabase-js', () => ({createClient: jest.fn()}));

import {createClient} from '@supabase/supabase-js';
import {GoogleSignin} from '@react-native-google-signin/google-signin';
import {supabase, getAuthHeaders, isAuthenticated} from '../supabase';
import {authService} from '../AuthService';
import {iapApi} from '../../iap/iapApi';

describe('local build without upstream cloud accounts', () => {
  it('rejects unconfigured purchase requests before fetch', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');
    try {
      await expect(iapApi.refresh('ios', [], {})).rejects.toThrow(
        'purchase service is not configured',
      );
      await expect(iapApi.binding()).rejects.toThrow(
        'purchase service is not configured',
      );
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      fetchSpy.mockRestore();
    }
  });

  it('does not create a Supabase client or configure Google sign-in', async () => {
    expect(supabase).toBeNull();
    expect(createClient).not.toHaveBeenCalled();
    expect(GoogleSignin.configure).not.toHaveBeenCalled();
    expect(authService.isAuthenticated).toBe(false);
    expect(await getAuthHeaders()).toEqual({});
    expect(await isAuthenticated()).toBe(false);
  });
});
