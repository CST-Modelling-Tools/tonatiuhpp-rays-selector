#include "SurfaceMap.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>
#include <vector>

SurfaceMap::SurfaceMap(const std::unordered_map<uint64_t, std::string>& surfaceData)
    : m_surfacePaths(surfaceData)
{
    for (const auto& [id, path] : surfaceData)
    {
        if (path.find("/Heliostats/") != std::string::npos)
        {
            m_heliostatNames[id] = extractHeliostatName(path);
        }
        else if (path.find("/Receivers/") != std::string::npos)
        {
            m_receiverNames[id] = extractReceiverName(path);
        }
    }
}

bool SurfaceMap::isHeliostat(uint64_t surfaceId) const
{
    return m_heliostatNames.find(surfaceId) != m_heliostatNames.end();
}

bool SurfaceMap::isReceiver(uint64_t surfaceId) const
{
    return m_receiverNames.find(surfaceId) != m_receiverNames.end();
}

std::string SurfaceMap::getHeliostatName(uint64_t surfaceId) const
{
    auto it = m_heliostatNames.find(surfaceId);
    return (it != m_heliostatNames.end()) ? it->second : "UnknownHeliostat";
}

std::string SurfaceMap::getReceiverName(uint64_t surfaceId) const
{
    auto it = m_receiverNames.find(surfaceId);
    return (it != m_receiverNames.end()) ? it->second : "UnknownReceiver";
}

std::size_t SurfaceMap::getReceiverCount() const
{
    return m_receiverNames.size();
}

std::size_t SurfaceMap::getHeliostatCount() const
{
    return m_heliostatNames.size();
}

std::size_t SurfaceMap::getTotalSurfaceCount() const
{
    return m_surfacePaths.size();
}

// Deterministic: names sorted by ascending receiver ID
std::vector<std::string> SurfaceMap::getReceiverNames() const
{
    std::vector<std::pair<uint64_t, std::string>> items;
    items.reserve(m_receiverNames.size());
    for (const auto& kv : m_receiverNames) items.emplace_back(kv.first, kv.second);

    std::sort(items.begin(), items.end(),
              [](const auto& a, const auto& b){ return a.first < b.first; });

    std::vector<std::string> names;
    names.reserve(items.size());
    for (const auto& kv : items) names.push_back(kv.second);
    return names;
}

// --- Helpers ---

// Extracts a heliostat label, preferring the segment immediately after "Heliostats".
std::string SurfaceMap::extractHeliostatName(const std::string& path) const
{
    // Tokenize by '/'
    std::vector<std::string> segs;
    {
        std::istringstream ss(path);
        std::string seg;
        while (std::getline(ss, seg, '/')) {
            if (!seg.empty()) segs.push_back(seg);
        }
    }

    // Find "Heliostats" segment and take the next segment if available
    for (std::size_t i = 0; i + 1 < segs.size(); ++i) {
        if (segs[i] == "Heliostats") {
            // e.g., "H012", "H101", etc.
            return segs[i + 1];
        }
    }

    // Fallback: last segment that looks like H\d+
    for (auto it = segs.rbegin(); it != segs.rend(); ++it) {
        const std::string& s = *it;
        if (!s.empty() && s[0] == 'H' && (s.size() >= 2) && std::isdigit(static_cast<unsigned char>(s[1]))) {
            return s;
        }
    }

    return "UnknownHeliostat";
}

// Extracts a receiver label, preferring the segment immediately after "Receivers".
std::string SurfaceMap::extractReceiverName(const std::string& path) const
{
    // Tokenize by '/'
    std::vector<std::string> segs;
    {
        std::istringstream ss(path);
        std::string seg;
        while (std::getline(ss, seg, '/')) {
            if (!seg.empty()) segs.push_back(seg);
        }
    }

    // Prefer the segment after "Receivers"
    for (std::size_t i = 0; i + 1 < segs.size(); ++i) {
        if (segs[i] == "Receivers") {
            return segs[i + 1];
        }
    }

    // Fallback: last segment containing "Receiver"
    for (auto it = segs.rbegin(); it != segs.rend(); ++it) {
        const std::string& s = *it;
        if (s.find("Receiver") != std::string::npos) {
            return s;
        }
    }

    return "UnknownReceiver";
}

const std::unordered_map<uint64_t, std::string>& SurfaceMap::getHeliostatNames() const
{
    return m_heliostatNames;
}

const std::unordered_map<uint64_t, std::string>& SurfaceMap::getReceiverNamesMap() const
{
    return m_receiverNames;
}