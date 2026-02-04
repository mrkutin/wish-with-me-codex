# Wish With Me - iOS App Specification

Complete workflow and internal flow documentation for building a native iOS app that mirrors the PWA functionality.

---

## Table of Contents

1. [App Overview](#1-app-overview)
2. [Tech Stack Recommendations](#2-tech-stack-recommendations)
3. [User Flows & Internal Mechanics](#3-user-flows--internal-mechanics)
4. [Screen Specifications](#4-screen-specifications)
5. [Data Models](#5-data-models)
6. [Offline-First Architecture](#6-offline-first-architecture)
7. [API Integration](#7-api-integration)
8. [Authentication Flows](#8-authentication-flows)
9. [Sync Engine](#9-sync-engine)
10. [Push Notifications](#10-push-notifications)
11. [Deep Linking](#11-deep-linking)
12. [Security Requirements](#12-security-requirements)
13. [Error Handling](#13-error-handling)
14. [Accessibility](#14-accessibility)

---

## 1. App Overview

**Wish With Me** is an offline-first wishlist app that allows users to:
- Create and manage wishlists with items
- Add items via URL (auto-extracts title, price, image)
- Share wishlists with view-only or mark permissions
- Mark items as "I'll get this" (hidden from wishlist owner - surprise mode)
- Work fully offline with automatic sync when online

**Production URLs:**
- Web: https://wishwith.me
- API: https://api.wishwith.me

---

## 2. Tech Stack Recommendations

| Component | Recommendation | Rationale |
|-----------|----------------|-----------|
| UI Framework | SwiftUI | Modern, declarative, iOS 15+ |
| Architecture | MVVM + Clean Architecture | Separation of concerns, testability |
| Local Database | Core Data or Realm | Offline-first, sync-friendly |
| Networking | URLSession + async/await | Native, modern Swift concurrency |
| Auth | Keychain Services | Secure token storage |
| OAuth | ASWebAuthenticationSession | Native OAuth flow |
| Image Caching | Kingfisher or SDWebImage | Performance, caching |
| State Management | Combine + ObservableObject | Reactive updates |

---

## 3. User Flows & Internal Mechanics

### 3.1 App Launch Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        APP LAUNCH                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Check Keychain for refresh_token                                │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        Token Found                      No Token
              │                               │
              ▼                               ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│ POST /api/v2/auth/refresh│      │ Show Landing Screen     │
│ with refresh_token       │      │ (IndexView)             │
└─────────────────────────┘      └─────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
 Success              Failure
    │                   │
    ▼                   ▼
┌─────────────┐  ┌─────────────────┐
│ Store new   │  │ Clear Keychain  │
│ tokens      │  │ Show Login      │
│ Schedule    │  └─────────────────┘
│ refresh     │
└─────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ GET /api/v2/auth/me → Store user profile                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Initialize Sync Engine → Pull all collections                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Show Main Tab View (WishlistsView)                              │
└─────────────────────────────────────────────────────────────────┘
```

**Internal Actions:**
1. `AppDelegate.didFinishLaunching` or SwiftUI `App.init`
2. `AuthManager.restoreSession()` reads Keychain
3. If token exists, call refresh API
4. On success: decode JWT, schedule background refresh 2 min before expiry
5. Initialize `SyncEngine.shared.start()`
6. Set root view to authenticated or unauthenticated state

---

### 3.2 Registration Flow

**User Actions:**
1. Tap "Create Account" on landing screen
2. Enter: Name, Email, Password (min 8 chars)
3. Tap "Register"
4. (Optional) Continue with Google/Apple

**Internal Flow:**
```swift
// 1. User taps Register
func register(name: String, email: String, password: String) async throws {
    // 2. Validate locally
    guard password.count >= 8 else { throw ValidationError.passwordTooShort }
    guard email.isValidEmail else { throw ValidationError.invalidEmail }

    // 3. API call
    let response = try await api.post("/api/v2/auth/register", body: [
        "name": name,
        "email": email,
        "password": password,
        "locale": Locale.current.languageCode ?? "en"
    ])

    // 4. Store tokens securely
    try KeychainManager.save(key: "access_token", value: response.accessToken)
    try KeychainManager.save(key: "refresh_token", value: response.refreshToken)

    // 5. Store user in memory
    UserManager.shared.currentUser = response.user

    // 6. Schedule token refresh
    scheduleTokenRefresh(expiresIn: response.expiresIn)

    // 7. Initialize sync
    await SyncEngine.shared.start()

    // 8. Check for pending share token (deep link)
    if let pendingToken = DeepLinkManager.pendingShareToken {
        navigator.navigate(to: .sharedWishlist(token: pendingToken))
        DeepLinkManager.pendingShareToken = nil
    } else {
        navigator.navigate(to: .wishlists)
    }
}
```

**API Request:**
```http
POST /api/v2/auth/register
Content-Type: application/json

{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "securepass123",
    "locale": "en"
}
```

**API Response:**
```json
{
    "user": {
        "_id": "user:550e8400-e29b-41d4-a716-446655440000",
        "email": "john@example.com",
        "name": "John Doe",
        "locale": "en",
        "created_at": "2024-01-15T10:30:00Z"
    },
    "access_token": "eyJhbG...",
    "refresh_token": "eyJhbG...",
    "expires_in": 900
}
```

---

### 3.3 Login Flow

**User Actions:**
1. Tap "Login" on landing screen
2. Enter: Email, Password
3. Tap "Sign In"
4. (Optional) Continue with Google/Apple

**Internal Flow:**
```swift
func login(email: String, password: String) async throws {
    // 1. API call
    let response = try await api.post("/api/v2/auth/login", body: [
        "email": email,
        "password": password
    ])

    // 2. Store tokens
    try KeychainManager.save(key: "access_token", value: response.accessToken)
    try KeychainManager.save(key: "refresh_token", value: response.refreshToken)

    // 3. Store user
    UserManager.shared.currentUser = response.user

    // 4. Schedule refresh
    scheduleTokenRefresh(expiresIn: response.expiresIn)

    // 5. Initialize sync
    await SyncEngine.shared.start()

    // 6. Navigate (same pending share logic as register)
}
```

**Error Handling:**
- `401 Unauthorized` → Show "Invalid email or password"
- Network error → Show "Unable to connect. Check your connection."

---

### 3.4 OAuth Login Flow (Google/Apple)

**User Actions:**
1. Tap "Continue with Google" or "Sign in with Apple"
2. System OAuth sheet appears
3. User authenticates with provider
4. Redirect back to app

**Internal Flow:**
```swift
func initiateOAuth(provider: OAuthProvider) async throws {
    // 1. Get authorization URL from backend
    let authURL = try await api.get("/api/v1/oauth/\(provider.rawValue)/authorize")

    // 2. Present ASWebAuthenticationSession
    let session = ASWebAuthenticationSession(
        url: authURL,
        callbackURLScheme: "wishwithme"
    ) { callbackURL, error in
        // 3. Extract code and state from callback
        guard let url = callbackURL,
              let code = url.queryParameter("code"),
              let state = url.queryParameter("state") else {
            throw OAuthError.invalidCallback
        }

        // 4. Exchange code for tokens
        Task {
            try await self.completeOAuth(provider: provider, code: code, state: state)
        }
    }

    session.presentationContextProvider = self
    session.prefersEphemeralWebBrowserSession = false
    session.start()
}

func completeOAuth(provider: OAuthProvider, code: String, state: String) async throws {
    // 5. Call backend callback endpoint
    let response = try await api.get(
        "/api/v1/oauth/\(provider.rawValue)/callback",
        queryParams: ["code": code, "state": state]
    )

    // 6. Store tokens and user (same as login)
    try KeychainManager.save(key: "access_token", value: response.accessToken)
    try KeychainManager.save(key: "refresh_token", value: response.refreshToken)
    UserManager.shared.currentUser = response.user

    // 7. Initialize sync and navigate
    await SyncEngine.shared.start()
    navigator.navigate(to: .wishlists)
}
```

**For Sign in with Apple:**
```swift
func handleSignInWithApple() {
    let provider = ASAuthorizationAppleIDProvider()
    let request = provider.createRequest()
    request.requestedScopes = [.email, .fullName]

    let controller = ASAuthorizationController(authorizationRequests: [request])
    controller.delegate = self
    controller.presentationContextProvider = self
    controller.performRequests()
}

// ASAuthorizationControllerDelegate
func authorizationController(controller: ASAuthorizationController,
                            didCompleteWithAuthorization authorization: ASAuthorization) {
    guard let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential,
          let identityToken = appleIDCredential.identityToken,
          let tokenString = String(data: identityToken, encoding: .utf8) else {
        return
    }

    // Send to backend for verification and user creation
    Task {
        try await api.post("/api/v1/oauth/apple/callback", body: [
            "identity_token": tokenString,
            "user_identifier": appleIDCredential.user,
            "email": appleIDCredential.email,
            "full_name": appleIDCredential.fullName?.formatted()
        ])
    }
}
```

---

### 3.5 Create Wishlist Flow

**User Actions:**
1. On Wishlists screen, tap "+" button
2. Enter: Name (required), Description (optional), Icon (picker)
3. Tap "Create"

**Internal Flow:**
```swift
func createWishlist(name: String, description: String?, icon: String) async throws {
    // 1. Generate document ID
    let wishlistId = "wishlist:\(UUID().uuidString)"
    let userId = UserManager.shared.currentUser!.id

    // 2. Create local document
    let wishlist = Wishlist(
        id: wishlistId,
        type: "wishlist",
        ownerId: userId,
        name: name,
        description: description,
        icon: icon,
        access: [userId],
        createdAt: Date(),
        updatedAt: Date()
    )

    // 3. Save to local database
    try LocalDatabase.shared.save(wishlist)

    // 4. Trigger sync (push to server)
    await SyncEngine.shared.sync()

    // 5. UI updates automatically via Combine/observation
}
```

**Document Structure (stored locally):**
```json
{
    "_id": "wishlist:550e8400-e29b-41d4-a716-446655440000",
    "type": "wishlist",
    "owner_id": "user:123...",
    "name": "Birthday Wishlist",
    "description": "Things I want for my birthday",
    "icon": "cake",
    "access": ["user:123..."],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 3.6 Add Item Flow (URL Resolution)

**User Actions:**
1. On Wishlist Detail screen, tap "Add Item"
2. Select "From URL" tab
3. Paste product URL (e.g., Amazon link)
4. Tap "Add"
5. See item appear with "Resolving..." status
6. Item updates automatically with resolved data

**Internal Flow:**
```swift
func addItemFromURL(wishlistId: String, url: String) async throws {
    // 1. Validate URL
    guard URL(string: url) != nil else {
        throw ValidationError.invalidURL
    }

    // 2. Generate document ID
    let itemId = "item:\(UUID().uuidString)"
    let userId = UserManager.shared.currentUser!.id

    // 3. Get wishlist to copy access array
    let wishlist = try LocalDatabase.shared.get(Wishlist.self, id: wishlistId)

    // 4. Create item with pending status
    let item = Item(
        id: itemId,
        type: "item",
        wishlistId: wishlistId,
        ownerId: userId,
        title: "Loading...",           // Placeholder until resolved
        sourceUrl: url,
        status: .pending,              // Server will pick this up
        skipResolution: false,
        access: wishlist.access,
        createdAt: Date(),
        updatedAt: Date()
    )

    // 5. Save locally
    try LocalDatabase.shared.save(item)

    // 6. Trigger sync
    await SyncEngine.shared.sync()

    // 7. Item resolver service (server-side) will:
    //    a. Watch CouchDB _changes feed for status: "pending"
    //    b. Claim item with optimistic locking
    //    c. Fetch URL with Playwright (handles JS-rendered pages)
    //    d. Extract HTML, clean it, send to LLM
    //    e. LLM extracts: title, description, price, currency, image
    //    f. Update item with resolved data, status: "resolved"
    //    g. Sync pulls updated item to iOS app
}
```

**Item Status State Machine:**
```
┌─────────┐     ┌─────────────┐     ┌──────────┐
│ pending │ ──▶ │ in_progress │ ──▶ │ resolved │
└─────────┘     └─────────────┘     └──────────┘
                      │
                      ▼
                ┌─────────┐
                │  error  │ ──▶ (user can retry)
                └─────────┘
```

**UI Updates:**
- `pending`: Show "Resolving..." with spinner
- `in_progress`: Show "Processing..." with spinner
- `resolved`: Show full item card with image, title, price
- `error`: Show error badge with "Retry" button

---

### 3.7 Add Item Flow (Manual Entry)

**User Actions:**
1. On Wishlist Detail screen, tap "Add Item"
2. Select "Manual" tab
3. Fill form: Title, Description, Price, Currency, Quantity, Image (optional)
4. Tap "Add"

**Internal Flow:**
```swift
func addItemManually(wishlistId: String, data: ItemFormData) async throws {
    let itemId = "item:\(UUID().uuidString)"
    let userId = UserManager.shared.currentUser!.id
    let wishlist = try LocalDatabase.shared.get(Wishlist.self, id: wishlistId)

    // For manual items, skip resolution
    let item = Item(
        id: itemId,
        type: "item",
        wishlistId: wishlistId,
        ownerId: userId,
        title: data.title,
        description: data.description,
        price: data.price,
        currency: data.currency,
        quantity: data.quantity,
        sourceUrl: data.sourceUrl,
        imageBase64: data.imageBase64,     // If user uploaded image
        status: .resolved,                  // Already complete
        skipResolution: true,               // Don't process on server
        access: wishlist.access,
        createdAt: Date(),
        updatedAt: Date()
    )

    try LocalDatabase.shared.save(item)
    await SyncEngine.shared.sync()
}
```

---

### 3.8 Share Wishlist Flow

**User Actions:**
1. On Wishlist Detail screen, tap share icon (or "..." menu → Share)
2. Sheet appears with options:
   - Link Type: "View only" or "Can mark items"
   - Expiry: "Never", "7 days", "30 days"
3. Tap "Create Link"
4. Share link appears with copy/share options
5. User taps share icon → iOS Share Sheet

**Internal Flow:**
```swift
func createShareLink(
    wishlistId: String,
    linkType: ShareLinkType,  // .view or .mark
    expiresInDays: Int?
) async throws -> ShareLink {
    // 1. API call to create share link
    let response = try await api.post(
        "/api/v1/wishlists/\(wishlistId)/share",
        body: [
            "link_type": linkType.rawValue,
            "expires_in_days": expiresInDays
        ]
    )

    // 2. Construct full URL
    let shareURL = "https://wishwith.me/s/\(response.token)"

    // 3. Return share link object
    return ShareLink(
        id: response.id,
        token: response.token,
        url: shareURL,
        linkType: linkType,
        expiresAt: response.expiresAt,
        createdAt: response.createdAt
    )
}

func presentShareSheet(url: String) {
    let activityVC = UIActivityViewController(
        activityItems: [URL(string: url)!],
        applicationActivities: nil
    )
    // Present the activity view controller
}
```

**Share Link Document (server-side):**
```json
{
    "_id": "share:abc123...",
    "type": "share",
    "wishlist_id": "wishlist:...",
    "owner_id": "user:...",
    "token": "xK7mN9pQ2r",
    "link_type": "mark",
    "expires_at": "2024-02-15T10:30:00Z",
    "granted_users": [],
    "access": ["user:owner..."]
}
```

---

### 3.9 View Shared Wishlist Flow

**User Actions:**
1. User receives share link (e.g., via iMessage)
2. Taps link → App opens (via Universal Link)
3. If not logged in: Shows preview + "Login to continue"
4. If logged in: Shows full wishlist with items

**Internal Flow:**
```swift
// Deep link handler
func handleShareLink(token: String) async {
    // 1. Check if user is authenticated
    guard AuthManager.shared.isAuthenticated else {
        // Store pending token, show login
        DeepLinkManager.pendingShareToken = token
        navigator.navigate(to: .login)
        return
    }

    // 2. Fetch preview (works without full auth)
    let preview = try await api.get("/api/v1/shared/\(token)/preview")

    // 3. Grant access (registers user as viewer)
    try await api.post("/api/v1/shared/\(token)/grant-access")

    // 4. Fetch full wishlist and items
    let sharedData = try await api.get("/api/v1/shared/\(token)")

    // 5. Navigate to shared wishlist view
    navigator.navigate(to: .sharedWishlist(
        token: token,
        wishlist: sharedData.wishlist,
        items: sharedData.items
    ))
}
```

---

### 3.10 Mark Item Flow (Surprise Mode)

**User Actions:**
1. On Shared Wishlist screen (with mark permission)
2. See item they want to mark
3. Tap "Mark as getting" button
4. If quantity > 1: Select how many they'll get
5. Item shows "You marked this" badge

**Internal Flow:**
```swift
func markItem(shareToken: String, itemId: String, quantity: Int) async throws {
    // 1. API call to mark
    try await api.post(
        "/api/v1/shared/\(shareToken)/items/\(itemId)/mark",
        body: ["quantity": quantity]
    )

    // 2. Create local mark document
    let markId = "mark:\(UUID().uuidString)"
    let userId = UserManager.shared.currentUser!.id

    let mark = Mark(
        id: markId,
        type: "mark",
        itemId: itemId,
        wishlistId: /* from item */,
        ownerId: /* wishlist owner */,
        markedBy: userId,
        quantity: quantity,
        // IMPORTANT: access array EXCLUDES owner (surprise mode)
        access: /* all viewers except owner */,
        createdAt: Date(),
        updatedAt: Date()
    )

    // 3. Save locally and sync
    try LocalDatabase.shared.save(mark)
    await SyncEngine.shared.sync()

    // 4. UI updates to show "You marked this"
}

func unmarkItem(shareToken: String, itemId: String) async throws {
    // 1. API call to unmark
    try await api.delete("/api/v1/shared/\(shareToken)/items/\(itemId)/mark")

    // 2. Delete local mark
    let mark = try LocalDatabase.shared.findMark(itemId: itemId, markedBy: userId)
    try LocalDatabase.shared.delete(mark)

    // 3. Sync
    await SyncEngine.shared.sync()
}
```

**Mark Visibility Rules:**
- Mark owner sees: "You marked this" on their view
- Other viewers see: "Already marked by X people" (count only)
- Wishlist owner sees: NOTHING (marks hidden from owner = surprise)

---

### 3.11 Bookmark Shared Wishlist Flow

**User Actions:**
1. On Shared Wishlist screen, tap "Save" or bookmark icon
2. Wishlist appears in "Shared With Me" tab

**Internal Flow:**
```swift
func bookmarkWishlist(shareToken: String) async throws {
    // 1. API call
    try await api.post("/api/v1/shared/\(shareToken)/bookmark")

    // 2. Create local bookmark
    let bookmarkId = "bookmark:\(UUID().uuidString)"
    let userId = UserManager.shared.currentUser!.id

    let bookmark = Bookmark(
        id: bookmarkId,
        type: "bookmark",
        userId: userId,
        shareId: shareId,
        wishlistId: wishlistId,
        ownerName: ownerName,
        wishlistName: wishlistName,
        access: [userId],
        createdAt: Date(),
        updatedAt: Date()
    )

    // 3. Save and sync
    try LocalDatabase.shared.save(bookmark)
    await SyncEngine.shared.sync()
}
```

---

### 3.12 Edit Profile Flow

**User Actions:**
1. Navigate to Profile screen
2. Edit: Name, Bio, Avatar (camera/photo library)
3. Tap "Save"

**Internal Flow:**
```swift
func updateProfile(name: String, bio: String?, avatar: UIImage?) async throws {
    var body: [String: Any] = [
        "name": name,
        "bio": bio ?? ""
    ]

    // Convert avatar to base64 if provided
    if let avatar = avatar,
       let imageData = avatar.jpegData(compressionQuality: 0.7) {
        body["avatar_base64"] = imageData.base64EncodedString()
    }

    // API call
    let updatedUser = try await api.patch("/api/v2/auth/me", body: body)

    // Update local user
    UserManager.shared.currentUser = updatedUser
}
```

---

### 3.13 Logout Flow

**User Actions:**
1. Navigate to Settings
2. Tap "Logout"
3. Confirm in alert

**Internal Flow:**
```swift
func logout() async {
    // 1. Best-effort server logout (revokes refresh token)
    if let refreshToken = KeychainManager.get(key: "refresh_token") {
        try? await api.post("/api/v2/auth/logout", body: [
            "refresh_token": refreshToken
        ])
    }

    // 2. Clear all local auth
    KeychainManager.delete(key: "access_token")
    KeychainManager.delete(key: "refresh_token")
    UserManager.shared.currentUser = nil

    // 3. Stop sync engine
    SyncEngine.shared.stop()

    // 4. Clear local database (optional - could keep for offline)
    LocalDatabase.shared.clear()

    // 5. Navigate to landing
    navigator.navigate(to: .landing)
}
```

---

## 4. Screen Specifications

### 4.1 Landing Screen (IndexView)

**Purpose:** Onboarding for unauthenticated users

**Layout:**
```
┌────────────────────────────────────────┐
│              [App Logo]                │
│           Wish With Me                 │
│                                        │
│    Create and share wishlists with     │
│    friends and family                  │
│                                        │
│    ┌──────────────────────────────┐   │
│    │      Create Account          │   │
│    └──────────────────────────────┘   │
│                                        │
│    ┌──────────────────────────────┐   │
│    │         Login                │   │
│    └──────────────────────────────┘   │
│                                        │
│    ──────── or continue with ──────── │
│                                        │
│    [Google]  [Apple]  [Yandex]        │
│                                        │
│    ┌──────────────────────────────┐   │
│    │  How It Works (expandable)   │   │
│    └──────────────────────────────┘   │
└────────────────────────────────────────┘
```

**Behavior:**
- If user already authenticated → redirect to Wishlists
- "How It Works" shows 3-step carousel

---

### 4.2 Login Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  [← Back]                              │
│                                        │
│              Welcome back              │
│                                        │
│    Email                               │
│    ┌──────────────────────────────┐   │
│    │ email@example.com            │   │
│    └──────────────────────────────┘   │
│                                        │
│    Password                            │
│    ┌──────────────────────────────┐   │
│    │ ••••••••              [👁]   │   │
│    └──────────────────────────────┘   │
│                                        │
│    ┌──────────────────────────────┐   │
│    │          Sign In             │   │
│    └──────────────────────────────┘   │
│                                        │
│    ──────── or continue with ──────── │
│                                        │
│    [Google]  [Apple]  [Yandex]        │
│                                        │
│    Don't have an account? Register    │
└────────────────────────────────────────┘
```

**Validation:**
- Email: Required, valid email format
- Password: Required

**Errors:**
- "Invalid email or password" for 401
- Network error handling

---

### 4.3 Register Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  [← Back]                              │
│                                        │
│            Create Account              │
│                                        │
│    Name                                │
│    ┌──────────────────────────────┐   │
│    │ John Doe                     │   │
│    └──────────────────────────────┘   │
│                                        │
│    Email                               │
│    ┌──────────────────────────────┐   │
│    │ email@example.com            │   │
│    └──────────────────────────────┘   │
│                                        │
│    Password                            │
│    ┌──────────────────────────────┐   │
│    │ ••••••••              [👁]   │   │
│    └──────────────────────────────┘   │
│    Min 8 characters                    │
│                                        │
│    ┌──────────────────────────────┐   │
│    │        Create Account        │   │
│    └──────────────────────────────┘   │
│                                        │
│    ──────── or continue with ──────── │
│                                        │
│    [Google]  [Apple]  [Yandex]        │
│                                        │
│    Already have an account? Login     │
└────────────────────────────────────────┘
```

**Validation:**
- Name: Required
- Email: Required, valid format, unique
- Password: Required, min 8 characters

---

### 4.4 Wishlists Screen (Main Tab)

**Layout:**
```
┌────────────────────────────────────────┐
│  My Wishlists                    [+]  │
├────────────────────────────────────────┤
│  [My Wishlists] [Shared With Me]      │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ 🎂  Birthday Wishlist           │ │
│  │     5 items • Created Jan 15    │ │
│  │                          [···]  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ 🎄  Christmas 2024              │ │
│  │     12 items • Created Dec 1    │ │
│  │                          [···]  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ 🏠  Home Decor                  │ │
│  │     3 items • Created Jan 20    │ │
│  │                          [···]  │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
│  [Wishlists] [Profile] [Settings]     │
└────────────────────────────────────────┘
```

**My Wishlists Tab:**
- Pull-to-refresh triggers sync
- Swipe left on card → Share
- Swipe right on card → Delete (with confirmation)
- Menu (···) → Edit, Share, Delete
- Tap card → Navigate to Wishlist Detail
- Empty state: "No wishlists yet. Create your first one!"

**Shared With Me Tab:**
- Shows bookmarked shared wishlists
- Cards show: Owner avatar, Owner name, Wishlist name
- Menu → View, Remove bookmark
- Tap card → Navigate to Shared Wishlist

---

### 4.5 Wishlist Detail Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  [←]  Birthday Wishlist    [···] [+]  │
├────────────────────────────────────────┤
│  Things I want for my birthday         │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [Image]  Sony Headphones        │ │
│  │          $299 • Qty: 1          │ │
│  │          ✓ Resolved      [···]  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [Image]  Nintendo Switch        │ │
│  │          $349 • Qty: 1          │ │
│  │          ⏳ Resolving...  [···]  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [?]      amazon.com/dp/B0C...   │ │
│  │          — • Qty: 1             │ │
│  │          ⚠ Error  [Retry] [···] │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

**Item Card States:**
- **Pending/In Progress:** Spinner, "Resolving..." text
- **Resolved:** Green checkmark, full product info
- **Error:** Red warning, "Retry" button

**Actions:**
- [+] → Add Item Sheet
- [···] header → Share, Edit Wishlist, Delete Wishlist
- [···] item → Edit Item, Delete Item
- Swipe left → Delete item
- Tap item → Item Detail (future: expandable view)

---

### 4.6 Add Item Sheet

**Layout:**
```
┌────────────────────────────────────────┐
│  Add Item                       [×]   │
├────────────────────────────────────────┤
│  [From URL]  [Manual]                  │
├────────────────────────────────────────┤
│                                        │
│  (FROM URL TAB)                        │
│                                        │
│  Product URL                           │
│  ┌──────────────────────────────────┐ │
│  │ https://amazon.com/dp/...       │ │
│  └──────────────────────────────────┘ │
│  Paste a link and we'll extract the   │
│  product details automatically         │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │           Add Item              │ │
│  └──────────────────────────────────┘ │
│                                        │
├────────────────────────────────────────┤
│  (MANUAL TAB)                          │
│                                        │
│  Title *                               │
│  ┌──────────────────────────────────┐ │
│  │ Sony WH-1000XM5                 │ │
│  └──────────────────────────────────┘ │
│                                        │
│  Description                           │
│  ┌──────────────────────────────────┐ │
│  │ Wireless noise-canceling...     │ │
│  └──────────────────────────────────┘ │
│                                        │
│  Price          Currency               │
│  ┌────────────┐ ┌──────────────────┐  │
│  │ 299        │ │ USD ▼           │  │
│  └────────────┘ └──────────────────┘  │
│                                        │
│  Quantity       Image                  │
│  ┌────────────┐ ┌──────────────────┐  │
│  │ [-] 1 [+] │ │ [Add Photo]     │  │
│  └────────────┘ └──────────────────┘  │
│                                        │
│  Source URL (optional)                 │
│  ┌──────────────────────────────────┐ │
│  │ https://...                     │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │           Add Item              │ │
│  └──────────────────────────────────┘ │
└────────────────────────────────────────┘
```

---

### 4.7 Share Wishlist Sheet

**Layout:**
```
┌────────────────────────────────────────┐
│  Share "Birthday Wishlist"      [×]   │
├────────────────────────────────────────┤
│                                        │
│  Create New Link                       │
│                                        │
│  Permission                            │
│  ○ View only - Can see items           │
│  ● Can mark - Can mark items as        │
│              "I'll get this"           │
│                                        │
│  Expires                               │
│  [Never ▼]                             │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │         Create Link             │ │
│  └──────────────────────────────────┘ │
│                                        │
├────────────────────────────────────────┤
│  Active Links                          │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ https://wishwith.me/s/xK7mN9p  │ │
│  │ Can mark • Never expires        │ │
│  │ [Copy] [Share] [QR]    [Delete] │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ https://wishwith.me/s/aB3cD4e  │ │
│  │ View only • Expires Feb 15      │ │
│  │ [Copy] [Share] [QR]    [Delete] │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

**Actions:**
- [Copy] → Copy link to clipboard, show toast
- [Share] → iOS Share Sheet
- [QR] → Show QR code modal
- [Delete] → Confirm and revoke link

---

### 4.8 Shared Wishlist Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  [←]  Birthday Wishlist        [Save] │
├────────────────────────────────────────┤
│  👤 Shared by John Doe                │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [Image]  Sony Headphones        │ │
│  │          $299 • Qty: 1          │ │
│  │                                  │ │
│  │  ┌────────────────────────────┐ │ │
│  │  │     Mark as getting        │ │ │
│  │  └────────────────────────────┘ │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [Image]  Nintendo Switch        │ │
│  │          $349 • Qty: 1          │ │
│  │  ✓ You marked this              │ │
│  │                                  │ │
│  │  ┌────────────────────────────┐ │ │
│  │  │         Unmark             │ │ │
│  │  └────────────────────────────┘ │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ [Image]  AirPods Pro            │ │
│  │          $249 • Qty: 2          │ │
│  │  ○ 1 already marked by others   │ │
│  │                                  │ │
│  │  How many? [-] 1 [+]            │ │
│  │  ┌────────────────────────────┐ │ │
│  │  │     Mark as getting        │ │ │
│  │  └────────────────────────────┘ │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

**Mark Status Badges:**
- "You marked this" (green) - user has marked
- "X already marked by others" (grey) - others have marked
- No badge - unmarked

**Quantity Selector:**
- Only shown when item quantity > 1
- Constrained to remaining available quantity

---

### 4.9 Profile Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  Profile                              │
├────────────────────────────────────────┤
│                                        │
│            ┌─────────┐                │
│            │  [👤]   │                │
│            │ [Edit]  │                │
│            └─────────┘                │
│                                        │
│  Name                                  │
│  ┌──────────────────────────────────┐ │
│  │ John Doe                        │ │
│  └──────────────────────────────────┘ │
│                                        │
│  Email                                 │
│  john@example.com (not editable)       │
│                                        │
│  Bio                                   │
│  ┌──────────────────────────────────┐ │
│  │ Gift enthusiast and collector   │ │
│  │                                  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │         Save Changes            │ │
│  └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

**Avatar Edit:**
- Tap avatar → Action Sheet: "Camera", "Photo Library", "Remove"
- Crop to square, compress, convert to base64

---

### 4.10 Settings Screen

**Layout:**
```
┌────────────────────────────────────────┐
│  Settings                             │
├────────────────────────────────────────┤
│                                        │
│  LANGUAGE                              │
│  ┌──────────────────────────────────┐ │
│  │ Language              English ▶ │ │
│  └──────────────────────────────────┘ │
│                                        │
│  CONNECTED ACCOUNTS                    │
│  ┌──────────────────────────────────┐ │
│  │ [G] Google                      │ │
│  │     Connected as john@gmail.com │ │
│  │                    [Disconnect] │ │
│  ├──────────────────────────────────┤ │
│  │ [A] Apple                       │ │
│  │     Not connected               │ │
│  │                       [Connect] │ │
│  ├──────────────────────────────────┤ │
│  │ [Y] Yandex                      │ │
│  │     Not connected               │ │
│  │                       [Connect] │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ACCOUNT                               │
│  ┌──────────────────────────────────┐ │
│  │ Logout                          │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Delete Account (destructive)    │ │
│  └──────────────────────────────────┘ │
│                                        │
│  VERSION                               │
│  Wish With Me v1.0.0 (build 100)      │
│                                        │
└────────────────────────────────────────┘
```

**Connected Accounts Rules:**
- Can disconnect if: has password OR has 2+ other social connections
- Cannot disconnect last auth method (show alert explaining why)

---

## 5. Data Models

### 5.1 Core Models

```swift
// MARK: - User
struct User: Codable, Identifiable {
    let id: String              // "user:uuid"
    let email: String
    var name: String
    var avatarBase64: String?
    var locale: String          // "en" or "ru"
    var bio: String?
    let createdAt: Date
    var updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case email, name
        case avatarBase64 = "avatar_base64"
        case locale, bio
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Wishlist
struct Wishlist: Codable, Identifiable {
    let id: String              // "wishlist:uuid"
    let type: String            // "wishlist"
    let ownerId: String         // "user:uuid"
    var name: String
    var description: String?
    var icon: String            // emoji or icon name
    var access: [String]        // ["user:uuid", ...]
    var deleted: Bool?          // soft delete
    let createdAt: Date
    var updatedAt: Date

    // Local-only fields
    var rev: String?            // _rev for conflict detection

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case rev = "_rev"
        case deleted = "_deleted"
        case type
        case ownerId = "owner_id"
        case name, description, icon, access
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Item
struct Item: Codable, Identifiable {
    let id: String              // "item:uuid"
    let type: String            // "item"
    let wishlistId: String      // "wishlist:uuid"
    let ownerId: String         // "user:uuid"
    var title: String
    var description: String?
    var price: Decimal?
    var currency: String?       // "USD", "RUB", etc.
    var quantity: Int
    var sourceUrl: String?
    var imageUrl: String?
    var imageBase64: String?
    var status: ItemStatus
    var skipResolution: Bool
    var access: [String]
    var deleted: Bool?
    let createdAt: Date
    var updatedAt: Date

    var rev: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case rev = "_rev"
        case deleted = "_deleted"
        case type
        case wishlistId = "wishlist_id"
        case ownerId = "owner_id"
        case title, description, price, currency, quantity
        case sourceUrl = "source_url"
        case imageUrl = "image_url"
        case imageBase64 = "image_base64"
        case status
        case skipResolution = "skip_resolution"
        case access
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

enum ItemStatus: String, Codable {
    case pending = "pending"
    case inProgress = "in_progress"
    case resolved = "resolved"
    case error = "error"
}

// MARK: - Mark (Surprise Mode)
struct Mark: Codable, Identifiable {
    let id: String              // "mark:uuid"
    let type: String            // "mark"
    let itemId: String          // "item:uuid"
    let wishlistId: String      // "wishlist:uuid"
    let ownerId: String         // wishlist owner (for exclusion)
    let markedBy: String        // "user:uuid" who marked
    var quantity: Int
    var access: [String]        // EXCLUDES owner!
    var deleted: Bool?
    let createdAt: Date
    var updatedAt: Date

    var rev: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case rev = "_rev"
        case deleted = "_deleted"
        case type
        case itemId = "item_id"
        case wishlistId = "wishlist_id"
        case ownerId = "owner_id"
        case markedBy = "marked_by"
        case quantity, access
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

// MARK: - Share Link
struct ShareLink: Codable, Identifiable {
    let id: String              // "share:uuid"
    let type: String            // "share"
    let wishlistId: String
    let ownerId: String
    let token: String           // short random token
    let linkType: ShareLinkType // view or mark
    var expiresAt: Date?
    var grantedUsers: [String]
    var access: [String]
    let createdAt: Date
    var updatedAt: Date

    var url: String {
        "https://wishwith.me/s/\(token)"
    }

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case type
        case wishlistId = "wishlist_id"
        case ownerId = "owner_id"
        case token
        case linkType = "link_type"
        case expiresAt = "expires_at"
        case grantedUsers = "granted_users"
        case access
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

enum ShareLinkType: String, Codable {
    case view = "view"
    case mark = "mark"
}

// MARK: - Bookmark
struct Bookmark: Codable, Identifiable {
    let id: String              // "bookmark:uuid"
    let type: String            // "bookmark"
    let userId: String          // "user:uuid"
    let shareId: String         // "share:uuid"
    let wishlistId: String      // "wishlist:uuid"
    var ownerName: String       // cached for display
    var wishlistName: String    // cached for display
    var access: [String]        // [userId]
    var deleted: Bool?
    let createdAt: Date
    var updatedAt: Date

    var rev: String?

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case rev = "_rev"
        case deleted = "_deleted"
        case type
        case userId = "user_id"
        case shareId = "share_id"
        case wishlistId = "wishlist_id"
        case ownerName = "owner_name"
        case wishlistName = "wishlist_name"
        case access
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}
```

### 5.2 API Response Models

```swift
// MARK: - Auth Response
struct AuthResponse: Codable {
    let user: User
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int          // seconds

    enum CodingKeys: String, CodingKey {
        case user
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
    }
}

// MARK: - Sync Response
struct SyncPullResponse<T: Codable>: Codable {
    let documents: [T]
    let totalCount: Int

    enum CodingKeys: String, CodingKey {
        case documents
        case totalCount = "total_count"
    }
}

struct SyncPushResponse: Codable {
    let accepted: Int
    let conflicts: [SyncConflict]
}

struct SyncConflict: Codable {
    let documentId: String
    let serverDocument: [String: Any]?
    let reason: String

    enum CodingKeys: String, CodingKey {
        case documentId = "document_id"
        case serverDocument = "server_document"
        case reason
    }
}

// MARK: - Shared Wishlist Response
struct SharedWishlistResponse: Codable {
    let wishlist: Wishlist
    let items: [SharedItem]
    let linkType: ShareLinkType
    let ownerName: String
    let ownerAvatarBase64: String?

    enum CodingKeys: String, CodingKey {
        case wishlist, items
        case linkType = "link_type"
        case ownerName = "owner_name"
        case ownerAvatarBase64 = "owner_avatar_base64"
    }
}

struct SharedItem: Codable, Identifiable {
    let id: String
    let title: String
    let description: String?
    let price: Decimal?
    let currency: String?
    let quantity: Int
    let sourceUrl: String?
    let imageBase64: String?
    let markedByMe: Int         // quantity marked by current user
    let markedByOthers: Int     // quantity marked by others (not visible to owner)

    enum CodingKeys: String, CodingKey {
        case id = "_id"
        case title, description, price, currency, quantity
        case sourceUrl = "source_url"
        case imageBase64 = "image_base64"
        case markedByMe = "marked_by_me"
        case markedByOthers = "marked_by_others"
    }
}

// MARK: - OAuth
struct OAuthProvider: Codable, Identifiable {
    let id: String              // "google", "yandex", "apple"
    let name: String            // "Google"
    let enabled: Bool
}

struct ConnectedAccount: Codable {
    let provider: String
    let email: String?
    let connectedAt: Date

    enum CodingKeys: String, CodingKey {
        case provider, email
        case connectedAt = "connected_at"
    }
}
```

---

## 6. Offline-First Architecture

### 6.1 Local Database Schema

Using Core Data or Realm, create entities matching the data models with additional sync metadata:

```swift
// Core Data Entity Attributes (example)
extension WishlistEntity {
    @NSManaged var id: String           // Primary key
    @NSManaged var rev: String?         // CouchDB revision
    @NSManaged var type: String
    @NSManaged var ownerId: String
    @NSManaged var name: String
    @NSManaged var descriptionText: String?
    @NSManaged var icon: String
    @NSManaged var accessJSON: String   // JSON array
    @NSManaged var isDeleted: Bool
    @NSManaged var createdAt: Date
    @NSManaged var updatedAt: Date

    // Sync metadata
    @NSManaged var needsPush: Bool      // Local changes not yet synced
    @NSManaged var lastSyncedAt: Date?  // When last synced with server
}
```

### 6.2 Database Operations

```swift
protocol LocalDatabaseProtocol {
    // CRUD
    func save<T: Syncable>(_ document: T) throws
    func get<T: Syncable>(_ type: T.Type, id: String) throws -> T?
    func delete<T: Syncable>(_ document: T) throws
    func findAll<T: Syncable>(_ type: T.Type, predicate: NSPredicate?) -> [T]

    // Sync support
    func getUnsyncedDocuments<T: Syncable>(_ type: T.Type) -> [T]
    func markAsSynced<T: Syncable>(_ document: T) throws
    func upsert<T: Syncable>(_ document: T) throws  // Insert or update by _id
    func bulkUpsert<T: Syncable>(_ documents: [T]) throws

    // Reconciliation
    func deleteDocumentsNotIn<T: Syncable>(_ type: T.Type, ids: Set<String>) throws
}

protocol Syncable: Codable, Identifiable {
    var id: String { get }
    var type: String { get }
    var updatedAt: Date { get set }
    var deleted: Bool? { get set }
}
```

### 6.3 Offline Queue

```swift
class OfflineQueue {
    private let database: LocalDatabaseProtocol

    // Track operations when offline
    func enqueue<T: Syncable>(operation: SyncOperation, document: T) {
        var doc = document
        doc.updatedAt = Date()
        try? database.save(doc)
        // Document automatically marked as needsPush
    }

    // Get pending operations for sync
    func getPendingDocuments<T: Syncable>(_ type: T.Type) -> [T] {
        return database.getUnsyncedDocuments(type)
    }
}

enum SyncOperation {
    case create
    case update
    case delete
}
```

---

## 7. API Integration

### 7.1 Network Layer

```swift
class APIClient {
    private let baseURL = "https://api.wishwith.me"
    private let session: URLSession
    private let authManager: AuthManager

    func request<T: Decodable>(
        method: HTTPMethod,
        path: String,
        body: Encodable? = nil,
        queryParams: [String: String]? = nil
    ) async throws -> T {
        var request = URLRequest(url: buildURL(path: path, queryParams: queryParams))
        request.httpMethod = method.rawValue

        // Add auth header if available
        if let token = authManager.accessToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Add body if provided
        if let body = body {
            request.httpBody = try JSONEncoder().encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let (data, response) = try await session.data(for: request)

        // Handle 401 - token refresh
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode == 401 {
            try await authManager.refreshToken()
            return try await self.request(method: method, path: path, body: body, queryParams: queryParams)
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

### 7.2 API Endpoints Reference

| Method | Path | Auth | Body | Response |
|--------|------|------|------|----------|
| **Auth** |
| POST | `/api/v2/auth/register` | No | `{name, email, password, locale}` | `AuthResponse` |
| POST | `/api/v2/auth/login` | No | `{email, password}` | `AuthResponse` |
| POST | `/api/v2/auth/refresh` | No | `{refresh_token}` | `AuthResponse` |
| POST | `/api/v2/auth/logout` | Yes | `{refresh_token}` | `{}` |
| GET | `/api/v2/auth/me` | Yes | - | `User` |
| PATCH | `/api/v2/auth/me` | Yes | `{name?, bio?, avatar_base64?}` | `User` |
| **OAuth** |
| GET | `/api/v1/oauth/providers` | No | - | `[OAuthProvider]` |
| GET | `/api/v1/oauth/{provider}/authorize` | No | - | Redirect URL |
| GET | `/api/v1/oauth/{provider}/callback` | No | `?code&state` | `AuthResponse` |
| POST | `/api/v1/oauth/{provider}/link/initiate` | Yes | - | `{authorization_url, state}` |
| DELETE | `/api/v1/oauth/{provider}/unlink` | Yes | - | `{}` |
| GET | `/api/v1/oauth/connected` | Yes | - | `[ConnectedAccount]` |
| **Sync** |
| GET | `/api/v2/sync/pull/{collection}` | Yes | - | `SyncPullResponse` |
| POST | `/api/v2/sync/push/{collection}` | Yes | `{documents: [...]}` | `SyncPushResponse` |
| **Share** |
| GET | `/api/v1/wishlists/{id}/share` | Yes | - | `[ShareLink]` |
| POST | `/api/v1/wishlists/{id}/share` | Yes | `{link_type, expires_in_days?}` | `ShareLink` |
| DELETE | `/api/v1/wishlists/{id}/share/{share_id}` | Yes | - | `{}` |
| **Shared** |
| GET | `/api/v1/shared/{token}/preview` | No | - | `{wishlist_name, owner_name, item_count}` |
| POST | `/api/v1/shared/{token}/grant-access` | Yes | - | `{}` |
| GET | `/api/v1/shared/{token}` | Yes | - | `SharedWishlistResponse` |
| POST | `/api/v1/shared/{token}/items/{id}/mark` | Yes | `{quantity}` | `{}` |
| DELETE | `/api/v1/shared/{token}/items/{id}/mark` | Yes | - | `{}` |
| POST | `/api/v1/shared/{token}/bookmark` | Yes | - | `Bookmark` |
| DELETE | `/api/v1/shared/{token}/bookmark` | Yes | - | `{}` |
| GET | `/api/v1/shared/bookmarks` | Yes | - | `[Bookmark]` |

---

## 8. Authentication Flows

### 8.1 Token Management

```swift
class AuthManager: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: User?

    private(set) var accessToken: String?
    private var refreshTimer: Timer?

    func setTokens(access: String, refresh: String, expiresIn: Int) {
        // Store access token in memory
        self.accessToken = access

        // Store refresh token securely in Keychain
        try? KeychainManager.save(key: "refresh_token", value: refresh)

        // Schedule proactive refresh 2 minutes before expiry
        let refreshTime = max(expiresIn - 120, 60)
        scheduleRefresh(after: refreshTime)

        isAuthenticated = true
    }

    func refreshToken() async throws {
        guard let refreshToken = KeychainManager.get(key: "refresh_token") else {
            throw AuthError.noRefreshToken
        }

        let response: AuthResponse = try await api.post(
            "/api/v2/auth/refresh",
            body: ["refresh_token": refreshToken]
        )

        setTokens(
            access: response.accessToken,
            refresh: response.refreshToken,
            expiresIn: response.expiresIn
        )
        currentUser = response.user
    }

    private func scheduleRefresh(after seconds: Int) {
        refreshTimer?.invalidate()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(seconds), repeats: false) { _ in
            Task {
                try? await self.refreshToken()
            }
        }
    }
}
```

### 8.2 Keychain Helper

```swift
class KeychainManager {
    private static let service = "com.wishwithme.app"

    static func save(key: String, value: String) throws {
        let data = value.data(using: .utf8)!

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        // Delete existing
        SecItemDelete(query as CFDictionary)

        // Add new
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }

    static func get(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }

        return value
    }

    static func delete(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
```

---

## 9. Sync Engine

### 9.1 Sync Manager

```swift
class SyncEngine: ObservableObject {
    static let shared = SyncEngine()

    @Published var isSyncing = false
    @Published var lastSyncError: Error?
    @Published var isOnline = true

    private let syncInterval: TimeInterval = 30  // seconds
    private var syncTimer: Timer?
    private let reachability = NetworkReachability()

    private let collections = ["wishlists", "items", "marks", "bookmarks"]

    func start() {
        // Monitor network
        reachability.startMonitoring { [weak self] isOnline in
            self?.isOnline = isOnline
            if isOnline {
                Task { await self?.sync() }
            }
        }

        // Start periodic sync
        syncTimer = Timer.scheduledTimer(withTimeInterval: syncInterval, repeats: true) { _ in
            Task { await self.sync() }
        }

        // Initial sync
        Task { await sync() }
    }

    func stop() {
        syncTimer?.invalidate()
        syncTimer = nil
        reachability.stopMonitoring()
    }

    @MainActor
    func sync() async {
        guard isOnline, !isSyncing else { return }

        isSyncing = true
        lastSyncError = nil

        do {
            // Push first (all collections)
            for collection in collections {
                try await push(collection: collection)
            }

            // Then pull (all collections)
            for collection in collections {
                try await pull(collection: collection)
            }
        } catch {
            lastSyncError = error
        }

        isSyncing = false
    }
}
```

### 9.2 Push Flow

```swift
extension SyncEngine {
    private func push(collection: String) async throws {
        // Get documents that need sync
        let documents: [any Syncable]
        switch collection {
        case "wishlists":
            documents = LocalDatabase.shared.getUnsyncedDocuments(Wishlist.self)
        case "items":
            documents = LocalDatabase.shared.getUnsyncedDocuments(Item.self)
        case "marks":
            documents = LocalDatabase.shared.getUnsyncedDocuments(Mark.self)
        case "bookmarks":
            documents = LocalDatabase.shared.getUnsyncedDocuments(Bookmark.self)
        default:
            return
        }

        guard !documents.isEmpty else { return }

        // Push to server
        let response: SyncPushResponse = try await api.post(
            "/api/v2/sync/push/\(collection)",
            body: ["documents": documents]
        )

        // Handle conflicts (server wins with LWW)
        for conflict in response.conflicts {
            if let serverDoc = conflict.serverDocument {
                // Accept server version
                try LocalDatabase.shared.upsert(serverDoc)
            }
            // If no server doc, keep local (will retry next sync)
        }

        // Mark successfully pushed docs as synced
        for doc in documents where !response.conflicts.contains(where: { $0.documentId == doc.id }) {
            try LocalDatabase.shared.markAsSynced(doc)
        }
    }
}
```

### 9.3 Pull Flow

```swift
extension SyncEngine {
    private func pull(collection: String) async throws {
        // Pull from server (server filters by access)
        let response: SyncPullResponse<[String: Any]> = try await api.get(
            "/api/v2/sync/pull/\(collection)"
        )

        // Upsert all documents
        let serverIds = Set(response.documents.map { $0["_id"] as! String })

        switch collection {
        case "wishlists":
            let wishlists = try response.documents.map { try Wishlist(from: $0) }
            try LocalDatabase.shared.bulkUpsert(wishlists)
            // Reconciliation: delete local docs not on server
            try LocalDatabase.shared.deleteDocumentsNotIn(Wishlist.self, ids: serverIds)

        case "items":
            let items = try response.documents.map { try Item(from: $0) }
            try LocalDatabase.shared.bulkUpsert(items)
            try LocalDatabase.shared.deleteDocumentsNotIn(Item.self, ids: serverIds)

        case "marks":
            let marks = try response.documents.map { try Mark(from: $0) }
            try LocalDatabase.shared.bulkUpsert(marks)
            try LocalDatabase.shared.deleteDocumentsNotIn(Mark.self, ids: serverIds)

        case "bookmarks":
            let bookmarks = try response.documents.map { try Bookmark(from: $0) }
            try LocalDatabase.shared.bulkUpsert(bookmarks)
            try LocalDatabase.shared.deleteDocumentsNotIn(Bookmark.self, ids: serverIds)

        default:
            break
        }
    }
}
```

### 9.4 Conflict Resolution

**Last-Write-Wins (LWW):**
```swift
// Server-side logic (for reference)
func resolveConflict(clientDoc: Document, serverDoc: Document) -> Document {
    if clientDoc.updatedAt > serverDoc.updatedAt {
        return clientDoc  // Client wins
    } else {
        return serverDoc  // Server wins
    }
}
```

**iOS Client:** Always accept server version on conflict (server handles LWW)

---

## 10. Push Notifications

### 10.1 Notification Types (Future Enhancement)

| Event | Notification | Deep Link |
|-------|--------------|-----------|
| Item marked | "Someone marked an item on your wishlist" | `/wishlists/{id}` |
| New share access | "You've been granted access to a wishlist" | `/s/{token}` |
| Item resolved | "Your item has been processed" | `/wishlists/{id}` |

### 10.2 Implementation

```swift
// APNs setup (future implementation)
class NotificationManager {
    func requestPermission() async -> Bool {
        let options: UNAuthorizationOptions = [.alert, .badge, .sound]
        return try await UNUserNotificationCenter.current().requestAuthorization(options: options)
    }

    func registerForRemoteNotifications() {
        UIApplication.shared.registerForRemoteNotifications()
    }

    func handleNotification(userInfo: [AnyHashable: Any]) {
        // Parse deep link and navigate
        if let deepLink = userInfo["deep_link"] as? String {
            DeepLinkManager.shared.handle(URL(string: deepLink)!)
        }
    }
}
```

---

## 11. Deep Linking

### 11.1 Universal Links Setup

**Associated Domains:**
```
applinks:wishwith.me
```

**apple-app-site-association (server-side):**
```json
{
    "applinks": {
        "apps": [],
        "details": [
            {
                "appID": "TEAMID.com.wishwithme.app",
                "paths": ["/s/*", "/wishlists/*"]
            }
        ]
    }
}
```

### 11.2 Deep Link Handler

```swift
class DeepLinkManager {
    static let shared = DeepLinkManager()

    var pendingShareToken: String?

    func handle(_ url: URL) {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
            return
        }

        let pathComponents = components.path.split(separator: "/")

        // Handle share links: /s/{token}
        if pathComponents.first == "s", pathComponents.count >= 2 {
            let token = String(pathComponents[1])
            handleShareLink(token: token)
        }

        // Handle wishlist links: /wishlists/{id}
        if pathComponents.first == "wishlists", pathComponents.count >= 2 {
            let wishlistId = String(pathComponents[1])
            handleWishlistLink(id: wishlistId)
        }
    }

    private func handleShareLink(token: String) {
        if AuthManager.shared.isAuthenticated {
            Task {
                await Navigator.shared.navigate(to: .sharedWishlist(token: token))
            }
        } else {
            // Store for after login
            pendingShareToken = token
            Navigator.shared.navigate(to: .login)
        }
    }

    private func handleWishlistLink(id: String) {
        guard AuthManager.shared.isAuthenticated else {
            Navigator.shared.navigate(to: .login)
            return
        }
        Navigator.shared.navigate(to: .wishlistDetail(id: id))
    }
}
```

### 11.3 URL Scheme (Fallback)

**Custom URL Scheme:** `wishwithme://`

```swift
// Info.plist
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>wishwithme</string>
        </array>
    </dict>
</array>
```

---

## 12. Security Requirements

### 12.1 Token Storage

| Token | Storage | Reason |
|-------|---------|--------|
| Access Token | Memory only | Short-lived, fast access |
| Refresh Token | Keychain | Long-lived, secure storage |
| User ID | Memory + UserDefaults | Non-sensitive, for routing |

### 12.2 Network Security

```swift
// Enforce TLS 1.2+
let config = URLSessionConfiguration.default
config.tlsMinimumSupportedProtocolVersion = .TLSv12

// Certificate pinning (optional, for high security)
class PinningDelegate: NSObject, URLSessionDelegate {
    func urlSession(_ session: URLSession,
                   didReceive challenge: URLAuthenticationChallenge,
                   completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        // Validate certificate against pinned public key
    }
}
```

### 12.3 Data Protection

```swift
// Core Data encryption
let container = NSPersistentContainer(name: "WishWithMe")
let storeDescription = container.persistentStoreDescriptions.first
storeDescription?.setOption(
    FileProtectionType.completeUntilFirstUserAuthentication as NSObject,
    forKey: NSPersistentStoreFileProtectionKey
)
```

### 12.4 Input Validation

```swift
extension String {
    var isValidEmail: Bool {
        let regex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,64}"
        return NSPredicate(format: "SELF MATCHES %@", regex).evaluate(with: self)
    }

    var isValidPassword: Bool {
        count >= 8 && count <= 128
    }

    var isValidURL: Bool {
        URL(string: self) != nil
    }
}
```

---

## 13. Error Handling

### 13.1 Error Types

```swift
enum AppError: LocalizedError {
    case network(underlying: Error)
    case unauthorized
    case forbidden
    case notFound
    case conflict(message: String)
    case validation(field: String, message: String)
    case server(code: String, message: String)
    case offline
    case unknown

    var errorDescription: String? {
        switch self {
        case .network:
            return "Unable to connect. Please check your internet connection."
        case .unauthorized:
            return "Session expired. Please log in again."
        case .forbidden:
            return "You don't have permission to perform this action."
        case .notFound:
            return "The requested item could not be found."
        case .conflict(let message):
            return message
        case .validation(_, let message):
            return message
        case .server(_, let message):
            return message
        case .offline:
            return "You're offline. Changes will sync when you're back online."
        case .unknown:
            return "Something went wrong. Please try again."
        }
    }
}
```

### 13.2 API Error Response Parsing

```swift
struct APIError: Codable {
    let error: ErrorDetail

    struct ErrorDetail: Codable {
        let code: String
        let message: String
        let details: [String: String]?
    }
}

// Error codes from backend
enum APIErrorCode: String {
    case BAD_REQUEST
    case UNAUTHORIZED
    case FORBIDDEN
    case NOT_FOUND
    case CONFLICT
    case INVALID_URL
    case SSRF_BLOCKED
    case TIMEOUT
    case INTERNAL_ERROR
}
```

### 13.3 Error UI

```swift
struct ErrorView: View {
    let error: AppError
    let retryAction: (() -> Void)?

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.red)

            Text(error.localizedDescription)
                .multilineTextAlignment(.center)

            if let retry = retryAction {
                Button("Try Again", action: retry)
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding()
    }
}
```

---

## 14. Accessibility

### 14.1 Requirements

- VoiceOver support for all interactive elements
- Dynamic Type support (font scaling)
- Sufficient color contrast (WCAG AA)
- Reduce Motion support
- Keyboard navigation for iPad

### 14.2 Implementation

```swift
// VoiceOver labels
Button(action: createWishlist) {
    Image(systemName: "plus")
}
.accessibilityLabel("Create new wishlist")
.accessibilityHint("Opens the create wishlist form")

// Dynamic Type
Text(wishlist.name)
    .font(.headline)
    .dynamicTypeSize(.large ... .accessibility5)

// Reduce Motion
@Environment(\.accessibilityReduceMotion) var reduceMotion

withAnimation(reduceMotion ? nil : .spring()) {
    // Animation
}
```

---

## Appendix A: Icon Reference

| Icon Name | System Name | Usage |
|-----------|-------------|-------|
| Add | `plus` | Create buttons |
| Back | `chevron.left` | Navigation back |
| Share | `square.and.arrow.up` | Share actions |
| Edit | `pencil` | Edit actions |
| Delete | `trash` | Delete actions |
| Menu | `ellipsis` | Context menus |
| Sync | `arrow.triangle.2.circlepath` | Sync status |
| Offline | `wifi.slash` | Offline indicator |
| Mark | `checkmark.circle.fill` | Mark as getting |
| Unmark | `checkmark.circle` | Unmark |
| Wishlist | `gift` | Default wishlist icon |
| Profile | `person.circle` | User profile |
| Settings | `gearshape` | Settings |
| Bookmark | `bookmark` | Save shared wishlist |
| Error | `exclamationmark.triangle` | Error states |
| Pending | `clock` | Pending resolution |

---

## Appendix B: Color Palette

| Name | Light Mode | Dark Mode | Usage |
|------|------------|-----------|-------|
| Primary | `#6200EE` | `#BB86FC` | Buttons, links |
| Secondary | `#03DAC6` | `#03DAC6` | Accents |
| Background | `#FFFFFF` | `#121212` | Screen backgrounds |
| Surface | `#F5F5F5` | `#1E1E1E` | Cards, sheets |
| Error | `#B00020` | `#CF6679` | Error states |
| Success | `#00C853` | `#00E676` | Success states |
| Text Primary | `#000000` | `#FFFFFF` | Main text |
| Text Secondary | `#666666` | `#AAAAAA` | Secondary text |

---

## Appendix C: Localization Keys

```swift
enum L10n {
    enum Auth {
        static let login = "auth.login"
        static let register = "auth.register"
        static let email = "auth.email"
        static let password = "auth.password"
        static let name = "auth.name"
        static let logout = "auth.logout"
    }

    enum Wishlists {
        static let title = "wishlists.title"
        static let create = "wishlists.create"
        static let empty = "wishlists.empty"
        static let sharedWithMe = "wishlists.shared_with_me"
    }

    enum Items {
        static let add = "items.add"
        static let fromUrl = "items.from_url"
        static let manual = "items.manual"
        static let resolving = "items.resolving"
        static let resolved = "items.resolved"
        static let error = "items.error"
        static let retry = "items.retry"
    }

    enum Sharing {
        static let share = "sharing.share"
        static let viewOnly = "sharing.view_only"
        static let canMark = "sharing.can_mark"
        static let copyLink = "sharing.copy_link"
        static let linkCopied = "sharing.link_copied"
    }

    enum Marks {
        static let markAsGetting = "marks.mark_as_getting"
        static let unmark = "marks.unmark"
        static let youMarked = "marks.you_marked"
        static let othersMarked = "marks.others_marked"
    }

    enum Errors {
        static let network = "errors.network"
        static let unauthorized = "errors.unauthorized"
        static let unknown = "errors.unknown"
    }
}
```

**Supported Languages:**
- English (en) - Default
- Russian (ru)

---

## Summary

This specification provides everything needed to build a native iOS app that fully mirrors the PWA functionality:

1. **Authentication:** Email/password and OAuth (Google, Apple, Yandex)
2. **Offline-first:** Local Core Data/Realm database with background sync
3. **Wishlists:** Full CRUD with sharing capabilities
4. **Items:** Manual entry and URL auto-resolution
5. **Sharing:** View/mark permission levels with surprise mode
6. **Deep linking:** Universal Links for share URLs
7. **Security:** Keychain token storage, TLS, input validation

The app should maintain feature parity with the PWA while providing a native iOS experience with platform-specific patterns and optimizations.
