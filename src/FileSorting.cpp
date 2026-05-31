#include "FileSorting.h"

#include <cctype>
#include <limits>
#include <string>

bool FileSorting::operator()(const fs::directory_entry& entry1,
                                 const fs::directory_entry& entry2) const
{
    const std::string a = entry1.path().filename().string();
    const std::string b = entry2.path().filename().string();

    const int na = TonatiuhFileNumber(a);
    const int nb = TonatiuhFileNumber(b);

    if (na != nb) return na < nb;               // numeric order when both (or one) have numbers
    return a < b;                                // deterministic tie-breaker (lexicographic)
}

int FileSorting::TonatiuhFileNumber(const std::string& filename) const
{
    // Find the last '.' (end of stem) and the last '_' before that.
    const std::size_t dot = filename.find_last_of('.');
    const std::size_t end = (dot == std::string::npos) ? filename.size() : dot;

    if (end == 0) return -1;

    const std::size_t us = filename.find_last_of('_', end - 1);
    if (us == std::string::npos || us + 1 >= end) return -1;

    // Parse consecutive digits starting at us+1 up to 'end'
    long long value = 0;
    bool has_digits = false;
    for (std::size_t i = us + 1; i < end; ++i) {
        unsigned char ch = static_cast<unsigned char>(filename[i]);
        if (!std::isdigit(ch)) {
            // stop at first non-digit (handles names like "photons_12backup.dat")
            break;
        }
        has_digits = true;
        value = value * 10 + (filename[i] - '0');
        // optional: guard overflow if you expect huge indices
        if (value > static_cast<long long>(std::numeric_limits<int>::max())) {
            return std::numeric_limits<int>::max();
        }
    }

    return has_digits ? static_cast<int>(value) : -1;
}