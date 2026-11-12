This document details the memory allocation instructions which would be provided in the various instruction files viz. `instructions_1.txt`, `instructions_2.txt`, and `instructions_3.txt`. Any kind of tampering of the data provided in these files are absolutely prohibited. 

The instruction files provide the instructions on how to allocate and deallocate memory blocks to the entities. The entities here refer to the programs or processes running inside the processor which would require a certain number of memory blocks to it in order to function. The memory blocks can be free, owned solely by a single entity or owned jointly by multiple entities together. The document constraints itself to 14 entities which would referred to as '1' to '14'. 

### Instruction Format:
The file follows the command format as:
Command | Entities | Memory Blocks

A separator '|' is supplied to denote the separation between the values and the instructions are always provided in terms of the memory blocks. The instruction maintains this syntax for every command except for a certain scenario in deallocation in which the absence of memory block data would indicate complete deallocation of the entity.  

### Instruction Commands:
The instructions provided in the file would consists of two commands viz. `ALLOC` and `DEALLOC`.
- `ALLOC` : This command is an instruction to allocate the provided memory value to the respective entities. The instruction file follows a constraint of using the memory blocks only present within the working memory area. i.e. 103 * 8 = 824. The total number of physically allocated working memory blocks must not be greater than 824. 

Different examples to detail reading of the instructions are provided as follows:
    - ALLOC | 1 | 35 : This command instructs to allocate 35 memory blocks to a single entity 1. If entity 1 is already allocated some memory blocks then this instruction would indicate that another 35 blocks must be allocated to the particular entity 1. 
    - ALLOC | 1, 2 | 16 : This indicates that the 16 memory blocks are to be jointly owned by entities 1 and 2. These blocks are in addition to the already owned blocks by the respective entities. i.e. e.g if entity 1 already owns 40 blocks and entity 2 owns 30 blocks then after this instruction, entity 1 would own 40 + 16 = 56 blocks, entity 2 would own 30 + 16 = 46 blocks and then 16 blocks are added to the jointly owned blocks section in the ground truth table. The ownership entity set are not ordering dependent. i.e. 1,3 and 3,1 both would mean, joint ownership of entities 1, and 3. 
- `DEALLOC` : This command is an instruction to free up some of the assigned memory from the entities. The document follows the constraint to not apply DEALLOC commands to entities which are yet to be allocated any memory blocks and not to instruct to deallocate more memory blocks than what the entity already owns. Different examples of the usage of this instruction are as:
    - DEALLOC | 1 | 4 : This is a simple instruction to free up 4 memory blocks from entity 1's blocks. So after this instruction if entity 1 had initially been allocated 40 blocks would result in 36 blocks now as 4 blocks are removed. 
    - DEALLOC | 1, 3 | 6 : This instruction demands to remove 6 blocks from the memory blocks jointly owned by 1 and 3. The document constraints itself from not to deallocate memory blocks from jointly owned if there are no such jointly owned blocks existing. 
    - DEALLOC | 5 : This instruction means that all currently allocated blocks whose complete owner set is exactly entity 5 are freed. Blocks jointly owned by entity 5 and other entities are not modified by this operation. 

The instructions define only the number of memory block allocation. The assignment of specific memory blocks to specific entities are decided by the allocation algorithm defined allocator.h and allocator.c. 
