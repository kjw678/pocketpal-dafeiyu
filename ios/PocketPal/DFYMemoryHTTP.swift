import Foundation
import CryptoKit
import React

// A dedicated ephemeral URLSession. React Native fetch may follow redirects
// before JS can inspect response.url; this transport refuses them natively.
@objc(DFYMemoryHTTP)
class DFYMemoryHTTP: NSObject {
    private let lock = NSLock()
    private var requests: [String: DFYMemoryRequest] = [:]

    @objc static func requiresMainQueueSetup() -> Bool { false }

    @objc(sha256:resolver:rejecter:)
    func sha256(_ value: String, resolve: RCTPromiseResolveBlock, reject: RCTPromiseRejectBlock) {
        guard value.utf8.count <= 24000 else {
            reject("DFY_BODY_LIMIT", "Request rejected.", nil)
            return
        }
        resolve(SHA256.hash(data: Data(value.utf8)).map { String(format: "%02x", $0) }.joined())
    }

    @objc(request:token:body:idempotencyKey:requestId:resolver:rejecter:)
    func request(_ rawURL: String, token: String, body: String, idempotencyKey: String,
                 requestId: String, resolve: @escaping RCTPromiseResolveBlock,
                 reject: @escaping RCTPromiseRejectBlock) {
        guard let components = URLComponents(string: rawURL), components.scheme == "https",
              components.host != nil, components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil,
              let url = components.url, body.utf8.count <= 24000,
              token.utf8.count >= 16, token.utf8.count <= 512,
              token.utf8.allSatisfy({ $0 >= 33 && $0 <= 126 }),
              requestId.range(of: "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$", options: .regularExpression) != nil,
              idempotencyKey.isEmpty || idempotencyKey.range(of: "^dfy-v1-[a-f0-9]{64}$", options: .regularExpression) != nil else {
            reject("DFY_INVALID_REQUEST", "Request rejected.", nil)
            return
        }
        lock.lock()
        guard requests.count < 4, requests[requestId] == nil else {
            lock.unlock()
            reject("DFY_BUSY", "Transport busy.", nil)
            return
        }
        let operation = DFYMemoryRequest(resolve: resolve, reject: reject) { [weak self] in
            guard let self = self else { return }
            self.lock.lock()
            self.requests.removeValue(forKey: requestId)
            self.lock.unlock()
        }
        requests[requestId] = operation
        lock.unlock()
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalAndRemoteCacheData, timeoutInterval: 15)
        request.httpMethod = "POST"
        request.httpShouldHandleCookies = false
        request.httpBody = Data(body.utf8)
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue(requestId, forHTTPHeaderField: "X-Request-ID")
        request.setValue("no-store", forHTTPHeaderField: "Cache-Control")
        if !idempotencyKey.isEmpty { request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key") }
        operation.start(request)
    }

    @objc(cancel:)
    func cancel(_ requestId: String) {
        lock.lock()
        let operation = requests[requestId]
        lock.unlock()
        operation?.cancel()
    }
}

private final class DFYMemoryRequest: NSObject, URLSessionDataDelegate, @unchecked Sendable {
    private let taskLock = NSLock()
    private var cancelRequested = false
    private var session: URLSession?
    private var task: URLSessionDataTask?
    private var data = Data()
    private var status: Int?
    private var failure: String?
    private let resolve: RCTPromiseResolveBlock
    private let reject: RCTPromiseRejectBlock
    private let done: () -> Void

    init(resolve: @escaping RCTPromiseResolveBlock, reject: @escaping RCTPromiseRejectBlock, done: @escaping () -> Void) {
        self.resolve = resolve
        self.reject = reject
        self.done = done
        super.init()
    }

    func start(_ request: URLRequest) {
        let config = URLSessionConfiguration.ephemeral
        config.urlCache = nil
        config.httpCookieStorage = nil
        config.urlCredentialStorage = nil
        config.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 20
        let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        self.session = session
        let task = session.dataTask(with: request)
        taskLock.lock()
        self.task = task
        let cancelled = cancelRequested
        taskLock.unlock()
        task.resume()
        if cancelled { task.cancel() }
    }

    func cancel() {
        taskLock.lock()
        cancelRequested = true
        let task = self.task
        taskLock.unlock()
        task?.cancel()
    }

    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) {
        failure = "DFY_REDIRECT_DENIED"
        completionHandler(nil)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask,
                    didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let response = response as? HTTPURLResponse,
              response.expectedContentLength <= 65536,
              response.mimeType?.lowercased() == "application/json" else {
            failure = "DFY_INVALID_RESPONSE"
            completionHandler(.cancel)
            return
        }
        status = response.statusCode
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive chunk: Data) {
        guard data.count + chunk.count <= 65536 else {
            failure = "DFY_RESPONSE_LIMIT"
            dataTask.cancel()
            return
        }
        data.append(chunk)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        defer {
            self.session?.finishTasksAndInvalidate()
            taskLock.lock()
            self.task = nil
            taskLock.unlock()
            self.session = nil
            done()
        }
        guard error == nil, failure == nil, let status = status,
              let body = String(data: data, encoding: .utf8) else {
            // Never log or return NSError.localizedDescription: it may contain
            // endpoint details. Native/JS errors are deliberately fixed codes.
            reject(failure ?? "DFY_TRANSPORT_FAILED", "Memory request failed.", nil)
            return
        }
        resolve(["status": status, "body": body])
    }
}
