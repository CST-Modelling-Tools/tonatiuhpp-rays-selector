#ifndef SURFACE_MAP_H
#define SURFACE_MAP_H

#include <cstdint>
#include <unordered_map>
#include <vector>
#include <string>

class SurfaceMap
{
public:
    // surfaceData: maps surfaceId -> full path (e.g., ".../Heliostats/H012/Facet_3" or ".../Receivers/ReceiverA/...")
    explicit SurfaceMap(const std::unordered_map<uint64_t, std::string>& surfaceData);

    bool isHeliostat(uint64_t surfaceId) const;
    bool isReceiver (uint64_t surfaceId) const;

    std::string getReceiverName (uint64_t surfaceId) const;
    std::string getHeliostatName(uint64_t surfaceId) const;

    std::size_t getReceiverCount()  const;
    std::size_t getHeliostatCount() const;
    std::size_t getTotalSurfaceCount() const;

    // Deterministic order: names sorted by ascending receiver ID
    std::vector<std::string> getReceiverNames() const;

    // Additional accessors (unchanged signature)
    const std::unordered_map<uint64_t, std::string>& getHeliostatNames() const;
    const std::unordered_map<uint64_t, std::string>& getReceiverNamesMap() const;

private:
    // Raw input (only used for accounting)
    std::unordered_map<uint64_t, std::string> m_surfacePaths;

    // Classified name maps
    std::unordered_map<uint64_t, std::string> m_heliostatNames; // facet/heliostat surfaceId -> "Hxxx..."
    std::unordered_map<uint64_t, std::string> m_receiverNames;  // receiver surfaceId       -> "Receiver..."

    // Helpers
    std::string extractHeliostatName(const std::string& path) const;
    std::string extractReceiverName (const std::string& path) const;
};

#endif // SURFACE_MAP_H