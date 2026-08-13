import SwiftUI

// Design spec (decided): fill #0FB5A8, corner radius 26pt, height 52pt (full-width token),
// label "Pay $<amount>" (verb-first, names the outcome).

private let payButtonFill = Color(red: 0x0F / 255, green: 0xB5 / 255, blue: 0xA8 / 255)
private let payButtonCornerRadius: CGFloat = 26
private let payButtonHeight: CGFloat = 52

enum PayButtonState: Equatable {
    case idle
    case loading
    /// Action can't proceed right now. Stays enabled — tapping surfaces `reason` via `onBlocked`
    /// instead of paying, per the no-silent-disable rule for money-moving buttons.
    case blocked(reason: String)
}

struct PayButton: View {
    let amount: Decimal
    var state: PayButtonState = .idle
    var onPay: () -> Void
    var onBlocked: (String) -> Void = { _ in }

    private var label: String {
        "Pay \(amount.formatted(.currency(code: "USD")))"
    }

    private var isLoading: Bool {
        state == .loading
    }

    var body: some View {
        Button(action: handleTap) {
            Group {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(.white)
                } else {
                    Text(label)
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(.white)
                }
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(PayButtonStyle(isBlocked: isBlocked))
        .disabled(isLoading)
        .frame(height: payButtonHeight)
        .accessibilityLabel(label)
    }

    private var isBlocked: Bool {
        if case .blocked = state { return true }
        return false
    }

    private func handleTap() {
        switch state {
        case .idle:
            onPay()
        case .blocked(let reason):
            onBlocked(reason)
        case .loading:
            break
        }
    }
}

private struct PayButtonStyle: ButtonStyle {
    var isBlocked: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .frame(height: payButtonHeight)
            .background(payButtonFill.opacity(isBlocked ? 0.6 : 1))
            .clipShape(RoundedRectangle(cornerRadius: payButtonCornerRadius, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

// MARK: - Example usage (pinned full-width above safe area, 16pt margins)

private struct CheckoutScreenExample: View {
    @State private var state: PayButtonState = .idle
    @State private var blockedMessage: String?

    var body: some View {
        VStack {
            Spacer()
            Text("Checkout")
        }
        .safeAreaInset(edge: .bottom) {
            PayButton(
                amount: 40.00,
                state: state,
                onPay: {
                    state = .loading
                },
                onBlocked: { reason in
                    blockedMessage = reason
                }
            )
            .padding(.horizontal, 16)
            .padding(.top, 12)
        }
        .alert("Can't pay yet", isPresented: Binding(
            get: { blockedMessage != nil },
            set: { if !$0 { blockedMessage = nil } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(blockedMessage ?? "")
        }
    }
}

#Preview("States") {
    VStack(spacing: 16) {
        PayButton(amount: 40.00, state: .idle, onPay: {})
        PayButton(amount: 40.00, state: .loading, onPay: {})
        PayButton(amount: 40.00, state: .blocked(reason: "Add a payment method to continue."), onPay: {}, onBlocked: { _ in })
    }
    .padding(.horizontal, 16)
}

#Preview("Checkout screen") {
    CheckoutScreenExample()
}
