#ifndef TONATIUHPHOTONREADER_H
#define TONATIUHPHOTONREADER_H

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct PhotonInfo
{
    std::uint64_t id = 0;
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    int side = 0;
    std::uint64_t previous_id = 0;
    std::uint64_t next_id = 0;
    std::uint64_t surface_id = 0;
};

class TonatiuhPhotonReader
{
public:
    explicit TonatiuhPhotonReader(fs::path directoryPath, std::string filePrefix = "photons");
    ~TonatiuhPhotonReader() = default;

    TonatiuhPhotonReader(const TonatiuhPhotonReader&) = delete;
    TonatiuhPhotonReader& operator=(const TonatiuhPhotonReader&) = delete;
    TonatiuhPhotonReader(TonatiuhPhotonReader&&) noexcept = default;
    TonatiuhPhotonReader& operator=(TonatiuhPhotonReader&&) noexcept = default;

    const std::vector<fs::directory_entry>& directoryEntries() const { return m_directoryEntries; }

    bool ReadPhotonInfo(PhotonInfo& photonInfo);

private:
    bool ReadPhotonInfoFromFile(PhotonInfo& photonInfo);
    bool OpenNextFile();
    bool matchesInputFilePrefix(const fs::path& path) const;

    fs::path m_directoryPath;
    std::string m_filePrefix;
    std::vector<fs::directory_entry> m_directoryEntries;
    std::size_t m_fileNumber = 0;
    bool m_firstPhoton = true;

    std::ifstream m_ifs;

    std::unique_ptr<char[]> m_buf;
    std::size_t m_bufSize = 0;
};

#endif // TONATIUHPHOTONREADER_H
