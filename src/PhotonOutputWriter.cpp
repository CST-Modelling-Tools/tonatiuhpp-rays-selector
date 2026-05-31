#include "PhotonOutputWriter.h"

#include <algorithm>
#include <iomanip>
#include <stdexcept>

PhotonOutputWriter::PhotonOutputWriter(std::filesystem::path outputDatFile,
                                       std::filesystem::path outputParametersFile,
                                       const ParametersFileReader& parameters)
    : m_outputDatFile(std::move(outputDatFile)),
      m_outputParametersFile(std::move(outputParametersFile)),
      m_parameters(parameters)
{
}

void PhotonOutputWriter::open()
{
    if (m_outputDatFile.has_parent_path()) {
        std::filesystem::create_directories(m_outputDatFile.parent_path());
    }
    if (m_outputParametersFile.has_parent_path()) {
        std::filesystem::create_directories(m_outputParametersFile.parent_path());
    }

    m_ofs.open(m_outputDatFile, std::ios::binary | std::ios::trunc);
    if (!m_ofs) {
        throw std::runtime_error("Unable to open output .dat file: " + m_outputDatFile.string());
    }
}

void PhotonOutputWriter::writeEscapedRay(const EscapedRayRecord& record)
{
    if (!m_ofs) {
        throw std::runtime_error("Output .dat file is not open.");
    }

    writeBigEndianDouble(m_ofs, record.x);
    writeBigEndianDouble(m_ofs, record.y);
    writeBigEndianDouble(m_ofs, record.z);
    writeBigEndianDouble(m_ofs, record.dx);
    writeBigEndianDouble(m_ofs, record.dy);
    writeBigEndianDouble(m_ofs, record.dz);
    ++m_selectedRayCount;
}

void PhotonOutputWriter::close()
{
    if (m_ofs.is_open()) {
        m_ofs.flush();
        if (!m_ofs) {
            throw std::runtime_error("Error while flushing output .dat file: " + m_outputDatFile.string());
        }
        m_ofs.close();
    }
    writeParametersFile();
}

void PhotonOutputWriter::writeBigEndianDouble(std::ofstream& ofs, double value)
{
    unsigned char bytes[sizeof(double)];
    static_assert(sizeof(double) == 8, "This writer expects 8-byte IEEE doubles.");
    std::copy(reinterpret_cast<unsigned char*>(&value),
              reinterpret_cast<unsigned char*>(&value) + sizeof(double),
              bytes);

#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    std::reverse(bytes, bytes + sizeof(double));
#endif

    ofs.write(reinterpret_cast<const char*>(bytes), sizeof(double));
    if (!ofs) {
        throw std::runtime_error("Error while writing output photon record.");
    }
}

void PhotonOutputWriter::writeParametersFile() const
{
    std::ofstream out(m_outputParametersFile, std::ios::trunc);
    if (!out) {
        throw std::runtime_error("Unable to open output parameters file: " + m_outputParametersFile.string());
    }

    out << "START PARAMETERS\n";
    out << "x\n";
    out << "y\n";
    out << "z\n";
    out << "dx\n";
    out << "dy\n";
    out << "dz\n";
    out << "END PARAMETERS\n";

    const double powerPerRay = m_parameters.getPowerPerPhoton();
    const double selectedPower = static_cast<double>(m_selectedRayCount) * powerPerRay;

    out << "\nSelectedRays\n";
    out << m_selectedRayCount << "\n";
    out << "\nPowerPerRay\n";
    out << std::setprecision(17) << powerPerRay << "\n";
    out << "\nSelectedPower\n";
    out << std::setprecision(17) << selectedPower << "\n";
}
