import axios from 'axios';
import {submitBenchmark} from '../benchmark';
import {
  submitFeedback,
  submitContentReport,
  submitModelLoadErrorReport,
} from '../feedback';
import {initializeAppCheck, getAppCheckToken} from '../../utils/fb';

jest.mock('axios');

describe('independent Dafeiyu cloud boundary', () => {
  it.each([
    () => submitBenchmark({} as any, {} as any),
    () => submitFeedback({} as any),
    () => submitContentReport({} as any),
    () => submitModelLoadErrorReport({} as any),
    () => initializeAppCheck(),
    () => getAppCheckToken(),
  ])(
    'rejects official submission without sending data or fabricating a token',
    async call => {
      await expect(call()).rejects.toThrow('unavailable in Dafeiyu');
      expect(axios.post).not.toHaveBeenCalled();
    },
  );
});
