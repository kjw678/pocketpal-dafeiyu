//
//  OpenPalChatIntent.swift
//  PocketPal
//
//  App Intent for opening a Pal's chat screen
//

import Foundation
import AppIntents
import UIKit

@available(iOS 16.0, *)
struct OpenPalChatIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Pal Chat"
    static var description = IntentDescription("Open Dafeiyu and start chatting with a specific Pal")

    static var openAppWhenRun: Bool = true // Open the app

    @Parameter(title: "Pal", description: "The Pal to chat with")
    var pal: PalEntity

    static var parameterSummary: some ParameterSummary {
        Summary("Open chat with \(\.$pal)")
    }

    @MainActor
    func perform() async throws -> some IntentResult {
        // Build deep link URL
        var urlComponents = URLComponents()
        urlComponents.scheme = "dafeiyu"
        urlComponents.host = "chat"

        // Only an opaque Pal identifier crosses this URL. Private messages
        // must use the native Ask Pal action, never URL query parameters.
        let queryItems: [URLQueryItem] = [
            URLQueryItem(name: "palId", value: pal.id)
        ]

        urlComponents.queryItems = queryItems

        guard let url = urlComponents.url else {
            throw OpenPalChatError.invalidURL
        }

        // Open the URL
        await UIApplication.shared.open(url)

        return .result()
    }
}

// MARK: - Errors

enum OpenPalChatError: Error, LocalizedError {
    case invalidURL

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Failed to create deep link URL"
        }
    }
}
