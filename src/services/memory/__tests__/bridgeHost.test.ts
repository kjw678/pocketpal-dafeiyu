import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  configureBridge,
  getBridgePreferences,
  makeMemoryContext,
} from '../bridgeHost';

// Keep storage spies explicit, as in the upstream host/store suites. The
// package-name mapper also catches the package's own mock subpath.
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn().mockResolvedValue(null),
  setItem: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('react-native-keychain', () => ({
  ACCESSIBLE: {WHEN_UNLOCKED_THIS_DEVICE_ONLY: 'WhenUnlockedThisDeviceOnly'},
  getGenericPassword: jest.fn(),
  setGenericPassword: jest.fn(),
  resetGenericPassword: jest.fn(),
}));

describe('Dafeiyu host credential and transcript boundary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Keychain.getGenericPassword as jest.Mock).mockResolvedValue(false);
    (Keychain.setGenericPassword as jest.Mock).mockResolvedValue({
      service: 'test',
    });
  });

  it('stores endpoint/token/scopes only in this-device unlocked Keychain', async () => {
    await configureBridge({
      baseUrl: 'https://memory.example.invalid',
      token: 'test-only-device-token',
      allowRecall: true,
      allowWrite: false,
    });
    const call = (Keychain.setGenericPassword as jest.Mock).mock.calls[0];
    expect(call[2].accessible).toBe('WhenUnlockedThisDeviceOnly');
    expect(JSON.parse(call[1]).token).toBe('test-only-device-token');
    expect(AsyncStorage.setItem).not.toHaveBeenCalled();
  });

  it('never exposes the stored token through preferences returned to settings', async () => {
    (Keychain.getGenericPassword as jest.Mock).mockResolvedValue({
      password: JSON.stringify({
        baseUrl: 'https://memory.example.invalid',
        token: 'test-only-device-token',
        allowRecall: true,
        allowWrite: false,
      }),
    });
    expect(await getBridgePreferences()).toEqual({
      baseUrl: 'https://memory.example.invalid',
      configured: true,
      allowRecall: true,
      allowWrite: false,
    });
  });

  it('will not reuse a credential when the destination changes', async () => {
    (Keychain.getGenericPassword as jest.Mock).mockResolvedValue({
      password: JSON.stringify({
        baseUrl: 'https://old.example.invalid',
        token: 'test-only-device-token',
      }),
    });
    await expect(
      configureBridge({
        baseUrl: 'https://new.example.invalid',
        token: '',
        allowRecall: true,
        allowWrite: true,
      }),
    ).rejects.toThrow();
    expect(Keychain.setGenericPassword).not.toHaveBeenCalled();
  });

  it('can retain a token only for the identical normalized endpoint', async () => {
    (Keychain.getGenericPassword as jest.Mock).mockResolvedValue({
      password: JSON.stringify({
        baseUrl: 'https://memory.example.invalid',
        token: 'test-only-device-token',
      }),
    });
    await configureBridge({
      baseUrl: 'https://memory.example.invalid/',
      token: '',
      allowRecall: true,
      allowWrite: false,
    });
    expect(
      JSON.parse((Keychain.setGenericPassword as jest.Mock).mock.calls[0][1])
        .token,
    ).toBe('test-only-device-token');
  });

  it('copies authentic host messages while excluding system rows and unknown authors', () => {
    const rows = [
      {
        id: 'a1',
        type: 'text',
        author: {id: 'a'},
        text: '我计划行动',
        createdAt: 2,
      },
      {
        id: 's1',
        type: 'text',
        author: {id: 'a'},
        text: '系统行',
        createdAt: 3,
        metadata: {system: true},
      },
      {
        id: 'x1',
        type: 'text',
        author: {id: 'unknown'},
        text: '未知',
        createdAt: 4,
      },
      {
        id: 'u1',
        type: 'text',
        author: {id: 'u'},
        text: '真实用户原文',
        createdAt: 1,
      },
    ];
    const c = makeMemoryContext('chat-1', rows, 'u', 'a');
    expect(c.sources.map(s => s.id)).toEqual(['u1', 'a1']);
    rows[3].text = '后续修改';
    expect(c.sources[0].text).toBe('真实用户原文');
  });
});
