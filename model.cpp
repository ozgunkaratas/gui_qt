#include "model.h"

#include <charconv>
#include <string>
#include <system_error>

namespace {

std::string_view trim(std::string_view s)
{
    constexpr std::string_view whitespace = " \t\r\n";
    const auto first = s.find_first_not_of(whitespace);
    if (first == std::string_view::npos)
        return {};
    const auto last = s.find_last_not_of(whitespace);
    return s.substr(first, last - first + 1);
}

} // namespace

std::optional<long long> Model::parseWholeNumber(std::string_view text) const
{
    text = trim(text);
    if (text.empty())
        return std::nullopt;

    // std::from_chars does not accept a leading '+', so strip it ourselves
    // (but don't let "+-5" slip through).
    if (text.front() == '+') {
        text.remove_prefix(1);
        if (text.empty() || text.front() == '-')
            return std::nullopt;
    }

    long long value{};
    const char* begin = text.data();
    const char* end   = text.data() + text.size();
    const auto [ptr, ec] = std::from_chars(begin, end, value);

    // ec != errc{}  -> not a number or out of range for long long
    // ptr != end    -> trailing garbage, e.g. "12abc" or "3.5"
    if (ec != std::errc{} || ptr != end)
        return std::nullopt;

    return value;
}

Sign Model::classify(long long value) const
{
    if (value < 0) return Sign::Negative;
    if (value > 0) return Sign::Positive;
    return Sign::Zero;
}

void Model::evaluate(const QString& text)
{
    const std::string utf8 = text.toStdString();   // keep the buffer alive for the string_view
    const auto parsed = parseWholeNumber(utf8);

    if (!parsed) {
        emit invalidInput(text);
        return;
    }
    emit resultReady(classify(*parsed));
}
