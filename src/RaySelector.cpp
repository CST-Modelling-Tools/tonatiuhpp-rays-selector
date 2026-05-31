#include "RaySelector.h"

#include <cmath>
#include <iostream>
#include <stdexcept>

RaySelector::RaySelector(const std::string& inputFolderPath, const std::string& photonFilePrefix)
    : m_inputFolderPath(inputFolderPath), m_photonFilePrefix(photonFilePrefix)
{
}

void RaySelector::selectEscapedReflectedRays(PhotonOutputWriter& writer)
{
    TonatiuhPhotonReader reader(m_inputFolderPath, m_photonFilePrefix);

    std::vector<PhotonInfo> ray;
    ray.reserve(32);

    PhotonInfo p{};
    while (reader.ReadPhotonInfo(p)) {
        ++m_totalPhotonsRead;
        ray.push_back(p);

        if (p.next_id != 0) {
            continue;
        }

        ++m_totalRaysRead;
        EscapedRayRecord record;
        if (makeEscapedRayRecord(ray, record)) {
            writer.writeEscapedRay(record);
            ++m_selectedRays;
        } else {
            ++m_skippedRays;
        }

        ray.clear();

        if (m_totalRaysRead % 1000000 == 0) {
            std::cout << "Processed " << m_totalRaysRead
                      << " rays; selected " << m_selectedRays << "...\n";
        }
    }

    if (!ray.empty()) {
        throw std::runtime_error("Input ended with an incomplete ray. Last photon did not have next ID == 0.");
    }
}

bool RaySelector::isEscapedReflectedRay(const std::vector<PhotonInfo>& ray)
{
    if (ray.size() < 2) {
        return false;
    }

    const PhotonInfo& last = ray.back();
    const PhotonInfo& previous = ray[ray.size() - 2];

    if (last.next_id != 0) {
        return false;
    }
    if (last.surface_id != 0) {
        return false;
    }
    if (previous.surface_id == 0) {
        return false;
    }

    return true;
}

bool RaySelector::makeEscapedRayRecord(const std::vector<PhotonInfo>& ray, EscapedRayRecord& record)
{
    if (!isEscapedReflectedRay(ray)) {
        return false;
    }

    const PhotonInfo& exit = ray.back();
    const PhotonInfo& origin = ray[ray.size() - 2];

    const double vx = exit.x - origin.x;
    const double vy = exit.y - origin.y;
    const double vz = exit.z - origin.z;
    const double norm = std::sqrt(vx * vx + vy * vy + vz * vz);
    if (!std::isfinite(norm) || norm <= 0.0) {
        return false;
    }

    record.x = origin.x;
    record.y = origin.y;
    record.z = origin.z;
    record.dx = vx / norm;
    record.dy = vy / norm;
    record.dz = vz / norm;
    return true;
}
