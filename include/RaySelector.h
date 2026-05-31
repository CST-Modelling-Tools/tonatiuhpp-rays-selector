#ifndef RAYSELECTOR_H
#define RAYSELECTOR_H

#include "PhotonOutputWriter.h"
#include "TonatiuhPhotonReader.h"

#include <cstdint>
#include <string>
#include <vector>

class RaySelector
{
public:
    explicit RaySelector(const std::string& inputFolderPath, const std::string& photonFilePrefix);

    void selectEscapedReflectedRays(PhotonOutputWriter& writer);

    std::uint64_t totalPhotonsRead() const { return m_totalPhotonsRead; }
    std::uint64_t totalRaysRead() const { return m_totalRaysRead; }
    std::uint64_t selectedRays() const { return m_selectedRays; }
    std::uint64_t skippedRays() const { return m_skippedRays; }

private:
    static bool isEscapedReflectedRay(const std::vector<PhotonInfo>& ray);
    static bool makeEscapedRayRecord(const std::vector<PhotonInfo>& ray, EscapedRayRecord& record);

    std::string m_inputFolderPath;
    std::string m_photonFilePrefix;
    std::uint64_t m_totalPhotonsRead = 0;
    std::uint64_t m_totalRaysRead = 0;
    std::uint64_t m_selectedRays = 0;
    std::uint64_t m_skippedRays = 0;
};

#endif // RAYSELECTOR_H
