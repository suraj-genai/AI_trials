In this task, we are refining and correcting the firmware code for simulating a memory allocation process in a customized processor system. This customized processor has a memory of 32KB which is organized as 128 columns of 256 bytes each. The fundamental memory unit of the processor is a memory block which is a 32 byte collection. There are 14 possible entities which can have allocated memory blocks allocated to them. Some memory blocks can be owned by one or multiple entities jointly. The allocation of the memory is directed as per the commands stated in the memory allocator contract files. 

The complete path to the workload files are:
`/app/workloads/instructions_1.txt`
`/app/workloads/instructions_2.txt`
`/app/workloads/instructions_3.txt` 

The procedure of reading these files are detailed in `/app/CONTRACT.md`.

The 32 KiB arena is the only persistent memory available to the allocator. Bounded automatic/stack buffers may be used for temporary API inputs, outputs, metadata encoding/decoding, and intermediate calculations. These buffers must not be used to retain allocator state or to provide additional persistent storage beyond the defined arena. The memory arena is formed of 128 columns of 256 bytes or 8 memory blocks are organized into 4 sections:

### Metadata Section:
The allocator must keep persistent allocator state within the memory arena. The metadata describes ownership of all 824 working blocks. Hence, a metadata section is required which would state the ownership of all 824 working blocks. It is desired for the metadata to be occupying only upto 224 bytes for fast operations and avoiding the requirement to borrow memory from other sections.

### Working Memory Section:
Columns 1 to 103 are assigned to be the working area and this constitutes the working memory for the processors. The memory is accessed from this area to be utilized for the processor operation.

### Scratchpad Section:
Columns 104 to 123 are declared as scratchpad areas which is utilized as temporary areas used in the requirement of movement, exchange, swapping and other related memory operations so the data from the blocks are not lost. The scratchpad contains 160 memory blocks which are not part of the allocatable working memory.

### Reserved Section: 
Column 124 to 127 are declared as reserved section in which it is assumed that extremely important firmware information for the processor is stored inside. Column 124 provides an extension area for serialized metadata when the metadata exceeds the 256-byte primary area. Metadata can use at most 256 additional bytes in this column, giving a maximum serialized metadata length of 512 bytes. Using this extension increases the metadata cost because serialized metadata beyond 256 bytes is charged under the higher-cost tier.

## Objective and Requirement
The firmware of the processor is expected to conduct the memory operations properly as per the input contracts. A ground truth value of entity ownership is also simultaneously created and the decoding of the metadata must match with the ground truth values. 

The repaired implementation must satisfy the following requirements:
1. The implementation must successfully execute for all the workload files (i.e. instruction files)
2. The implementation must preserve payload and data integrity
3. The implementation must maintain correct ownership of the memory blocks to the entities joint and single.
4. The metadata decoding must match the expected block ownerships.
5. The implementation must preserve the protected firmware state.
6. Persistent allocator state must stay within the defined memory region. Bounded automatic/stack buffers may be used for temporary operations as described above, but must not provide additional persistent storage.
7. The implementation must produce a cost score lower than or equal to 50000. 


In addition to that the memory movements also generate a cost score which are calculated based on the formula as explained in the following. 

If L is the length of the committed metadata (in bytes) after an instruction, the metadata penalty score P_m for that instruction is calculated as:

For 0 < L <= 224: P_m = L

For 224 < L <= 256: P_m = 224 + 4 * (L - 224)^2

For 256 < L <= 512: P_m = 4320 + 2500 * ceil((L - 256) / 32) + 50 * (L - 256)

Metadata lengths above 512 bytes are not allowed.

For memory movements, every physical block transfer of a 32-byte block adds a penalty of 25 points (P_move = 25 * M, where M is the total number of block transfers). The final cost score is the sum of the metadata penalties across all instructions plus the total movement penalty.
The total score is the sum of metadata and physical movement penalties across the complete workload:

P_total = sum(P_m(L_i)) + 25 * M

In addition to the integrity validation, the total cost score for the complete workloads together is expected to be less than or equal to 50000. 

The following constraints must be respected throughout the implementation and verification process:

1. Do not change the physical arena size of 32 KB.
2. Do not change the 128-column organization or the designated section capacities.
3. Do not change the payload, scratchpad, metadata extension, or protected-region boundaries.
4. Do not introduce an external persistent memory-management mechanism.
5. Do not modify or replace the trusted firmware memory implementation.
6. Do not modify the supplied workload instruction files.
7. Do not modify, weaken, or bypass the trusted verification criteria.
8. Do not compromise payload integrity, ownership consistency, metadata reconstruction, or protected-region integrity.

Changes should be confined to the editable allocator and metadata implementation unless explicitly required by the supplied interface.

After completion of the implementation, a compilation and verification report in accordance with the requirements described in `/app/Artifacts.md` is required to be produced. The report must document the build outcome, workload execution results, integrity verification, and final performance score.