#include "ParametersFileReader.h"
#include "PhotonOutputWriter.h"
#include "RaySelector.h"

#include <exception>
#include <filesystem>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

namespace
{
void printUsage(const char* program)
{
    std::cerr
        << "Usage:\n"
        << "  " << program << " <input_folder> <output_prefix> [parameters_file]\n\n"
        << "Example:\n"
        << "  " << program << " ./photon_output escaped_rays\n"
        << "  " << program << " ./photon_output escaped_rays PhotonMap_parameters.txt\n\n"
        << "The program selects complete rays whose last photon is in air "
        << "(surface ID 0) and whose previous photon is on a scene surface.\n"
        << "It writes <output_prefix>.dat and <output_prefix>_parameters.txt.\n";
}
}

int main(int argc, char* argv[])
{
    if (argc < 3 || argc > 4) {
        printUsage(argv[0]);
        return 1;
    }

    try {
        const std::string inputFolder = argv[1];
        const std::string outputPrefix = argv[2];
        const std::string parametersFile = (argc == 4) ? argv[3] : "";

        ParametersFileReader parameters(inputFolder, parametersFile);
        parameters.read();

        const fs::path outputDatFile = fs::path(outputPrefix + ".dat");
        const fs::path outputParametersFile = fs::path(outputPrefix + "_parameters.txt");

        std::cout << "Parameters file: " << parameters.getParametersFilePath().string() << "\n";
        std::cout << "Photon file prefix: " << parameters.getPhotonFilePrefix() << "\n";
        std::cout << "Power per photon: " << parameters.getPowerPerPhoton() << "\n";

        PhotonOutputWriter writer(outputDatFile, outputParametersFile, parameters);
        writer.open();

        RaySelector selector(inputFolder, parameters.getPhotonFilePrefix());
        selector.selectEscapedReflectedRays(writer);

        writer.close();

        std::cout << "Finished.\n";
        std::cout << "  Photons read: " << selector.totalPhotonsRead() << "\n";
        std::cout << "  Rays read: " << selector.totalRaysRead() << "\n";
        std::cout << "  Selected rays: " << selector.selectedRays() << "\n";
        std::cout << "  Output records: " << writer.selectedRayCount() << "\n";
        std::cout << "  Output .dat: " << outputDatFile.string() << "\n";
        std::cout << "  Output parameters: " << outputParametersFile.string() << "\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 2;
    }
}
