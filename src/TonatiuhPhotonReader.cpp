#include "TonatiuhPhotonReader.h"

#include "FileSorting.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

template <class T>
inline void endswap(T* objp)
{
    unsigned char* memp = reinterpret_cast<unsigned char*>(objp);
    std::reverse(memp, memp + sizeof(T));
}

static bool readBigEndianDouble(std::ifstream& ifs, double& out)
{
    ifs.read(reinterpret_cast<char*>(&out), sizeof(out));
    if (!ifs) {
        return false;
    }
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    endswap(&out);
#endif
    return true;
}

TonatiuhPhotonReader::TonatiuhPhotonReader(fs::path directoryPath, std::string filePrefix)
    : m_directoryPath(std::move(directoryPath)), m_filePrefix(std::move(filePrefix))
{
    if (!fs::exists(m_directoryPath) || !fs::is_directory(m_directoryPath)) {
        throw std::runtime_error("Input folder does not exist or is not a directory: " + m_directoryPath.string());
    }

    for (auto& p : fs::directory_iterator(m_directoryPath)) {
        if (!p.is_regular_file()) {
            continue;
        }
        if (p.path().extension() != ".dat") {
            continue;
        }
        if (!matchesInputFilePrefix(p.path())) {
            continue;
        }
        m_directoryEntries.push_back(p);
    }

    std::sort(m_directoryEntries.begin(), m_directoryEntries.end(), FileSorting{});

    if (m_directoryEntries.empty()) {
        throw std::runtime_error("No input .dat photon files found for prefix '" + m_filePrefix
                                 + "' in folder: " + m_directoryPath.string());
    }

    m_bufSize = 1024u * 1024u;
    m_buf = std::unique_ptr<char[]>(new char[m_bufSize]);
}

bool TonatiuhPhotonReader::matchesInputFilePrefix(const fs::path& path) const
{
    const std::string stem = path.stem().string();
    if (stem == m_filePrefix) {
        return true;
    }
    const std::string splitPrefix = m_filePrefix + "_";
    return stem.rfind(splitPrefix, 0) == 0;
}

bool TonatiuhPhotonReader::OpenNextFile()
{
    if (m_fileNumber >= m_directoryEntries.size()) {
        return false;
    }

    if (m_ifs.is_open()) {
        m_ifs.close();
    }
    m_ifs.clear();

    m_ifs.rdbuf()->pubsetbuf(m_buf.get(), static_cast<std::streamsize>(m_bufSize));

    const auto& path = m_directoryEntries[m_fileNumber].path();
    m_ifs.open(path, std::ios::binary);
    if (!m_ifs.is_open()) {
        std::cerr << "Failed to open photon file: " << path << "\n";
        return false;
    }

    std::cout << "Reading " << path.string() << "\n";
    return true;
}

bool TonatiuhPhotonReader::ReadPhotonInfo(PhotonInfo& photonInfo)
{
    if (m_firstPhoton) {
        m_firstPhoton = false;
        if (!OpenNextFile()) {
            return false;
        }
    }

    while (true) {
        if (ReadPhotonInfoFromFile(photonInfo)) {
            return true;
        }

        if (!m_ifs.eof()) {
            m_ifs.clear();
        }

        if (m_fileNumber + 1 < m_directoryEntries.size()) {
            ++m_fileNumber;
            if (!OpenNextFile()) {
                return false;
            }
            continue;
        }

        return false;
    }
}

bool TonatiuhPhotonReader::ReadPhotonInfoFromFile(PhotonInfo& p)
{
    double d_id = 0.0;
    double d_x = 0.0;
    double d_y = 0.0;
    double d_z = 0.0;
    double d_side = 0.0;
    double d_prev = 0.0;
    double d_next = 0.0;
    double d_surface = 0.0;

    const std::streampos before = m_ifs.tellg();

    if (!readBigEndianDouble(m_ifs, d_id))      { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_x))       { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_y))       { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_z))       { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_side))    { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_prev))    { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_next))    { m_ifs.clear(); m_ifs.seekg(before); return false; }
    if (!readBigEndianDouble(m_ifs, d_surface)) { m_ifs.clear(); m_ifs.seekg(before); return false; }

    p.id = static_cast<std::uint64_t>(std::llround(d_id));
    p.x = d_x;
    p.y = d_y;
    p.z = d_z;
    p.side = static_cast<int>(std::lrint(d_side));
    p.previous_id = static_cast<std::uint64_t>(std::llround(d_prev));
    p.next_id = static_cast<std::uint64_t>(std::llround(d_next));
    p.surface_id = static_cast<std::uint64_t>(std::llround(d_surface));

    return true;
}
