#ifndef PHOTONOUTPUTWRITER_H
#define PHOTONOUTPUTWRITER_H

#include "ParametersFileReader.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>

struct EscapedRayRecord
{
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double dx = 0.0;
    double dy = 0.0;
    double dz = 0.0;
};

class PhotonOutputWriter
{
public:
    PhotonOutputWriter(std::filesystem::path outputDatFile,
                       std::filesystem::path outputParametersFile,
                       const ParametersFileReader& parameters);

    void open();
    void writeEscapedRay(const EscapedRayRecord& record);
    void close();

    std::uint64_t selectedRayCount() const { return m_selectedRayCount; }

private:
    static void writeBigEndianDouble(std::ofstream& ofs, double value);
    void writeParametersFile() const;

    std::filesystem::path m_outputDatFile;
    std::filesystem::path m_outputParametersFile;
    const ParametersFileReader& m_parameters;
    std::ofstream m_ofs;
    std::uint64_t m_selectedRayCount = 0;
};

#endif // PHOTONOUTPUTWRITER_H
