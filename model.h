#pragma once

#include <QObject>
#include <QString>

#include <optional>
#include <string_view>

// The MODEL: logic only. It depends on QtCore (for QObject/signals) but never
// on QtWidgets, so it still knows nothing about dialogs, labels or colours.

enum class Sign { Negative, Zero, Positive };

class Model : public QObject {
    Q_OBJECT

public:
    explicit Model(QObject* parent = nullptr) : QObject(parent) {}

    // Pure helpers, still directly unit-testable without any event loop.
    std::optional<long long> parseWholeNumber(std::string_view text) const;
    Sign classify(long long value) const;

public slots:
    // Entry point for the view: "here is what the user typed, please evaluate it".
    // The model answers by emitting exactly one of the two signals below.
    void evaluate(const QString& text);

signals:
    void invalidInput(const QString& text);   // text was not a whole number
    void resultReady(Sign sign);              // text was valid, here is its sign
};
