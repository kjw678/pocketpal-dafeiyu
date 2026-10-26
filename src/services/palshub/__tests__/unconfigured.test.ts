jest.mock('@env', () => ({APP_URL: 'dafeiyu://app'}));
jest.mock('@supabase/supabase-js', () => ({createClient: jest.fn()}));

import {createClient} from '@supabase/supabase-js';
import {GoogleSignin} from '@react-native-google-signin/google-signin';
import {supabase, getAuthHeaders, isAuthenticated} from '../supabase';
import {authService} from '../AuthService';

describe('local build without upstream cloud accounts', () => {
  it('does not create a Supabase client or configure Google sign-in', async () => {
    expect(supabase).toBeNull();
    expect(createClient).not.toHaveBeenCalled();
    expect(GoogleSignin.configure).not.toHaveBeenCalled();
    expect(authService.isAuthenticated).toBe(false);
    expect(await getAuthHeaders()).toEqual({});
    expect(await isAuthenticated()).toBe(false);
  });
});
