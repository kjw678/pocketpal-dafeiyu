#import <React/RCTBridgeModule.h>

@interface RCT_EXTERN_MODULE(DFYMemoryHTTP, NSObject)
RCT_EXTERN_METHOD(sha256:(NSString *)value
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
RCT_EXTERN_METHOD(request:(NSString *)url
                  token:(NSString *)token
                  body:(NSString *)body
                  idempotencyKey:(NSString *)idempotencyKey
                  requestId:(NSString *)requestId
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject)
RCT_EXTERN_METHOD(cancel:(NSString *)requestId)
@end
